from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import argparse
import importlib.metadata
import json
import os
import time
from pathlib import Path

from starter.retrieval.dense import (
    CACHE_SCHEMA_VERSION,
    DenseConfig,
    PRODUCT_TEXT_TEMPLATE,
    QUERY_TEXT_TEMPLATE,
    file_sha256,
    product_text,
)


def load_catalog(path: Path) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    texts: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            product = json.loads(line)
            parent_asin = str(product.get("parent_asin") or "").strip()
            if not parent_asin or parent_asin in seen:
                raise ValueError(f"invalid parent_asin at catalog line {line_number}")
            seen.add(parent_asin)
            ids.append(parent_asin)
            texts.append(product_text(product))
    return ids, texts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the reproducible local MiniLM cache.")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--cache-dir", default="embeddings/minilm-l6-v2-v1")
    parser.add_argument("--model-cache-dir", default="models/huggingface/hub")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Allow the pinned model revision to be downloaded into the local model cache.",
    )
    args = parser.parse_args()

    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    if args.batch_size < 1:
        raise ValueError("batch size must be positive")
    catalog_path = Path(args.catalog)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    config = DenseConfig(
        cache_dir=cache_dir,
        model_cache_dir=Path(args.model_cache_dir),
    )
    ids, texts = load_catalog(catalog_path)
    started = time.perf_counter()
    model = SentenceTransformer(
        config.model_id,
        revision=config.model_revision,
        cache_folder=str(config.model_cache_dir),
        local_files_only=not args.allow_model_download,
    )
    vectors = model.encode(
        texts,
        batch_size=args.batch_size,
        normalize_embeddings=config.normalized,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype(config.dtype, copy=False)
    if vectors.shape != (len(ids), config.dimension):
        raise ValueError(f"unexpected embedding shape: {vectors.shape}")
    build_seconds = time.perf_counter() - started

    vectors_path = cache_dir / "vectors.npy"
    ids_path = cache_dir / "ids.json"
    np.save(vectors_path, vectors, allow_pickle=False)
    ids_path.write_text(json.dumps(ids) + "\n", encoding="utf-8")
    metadata = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "catalog_sha256": file_sha256(catalog_path),
        "model_id": config.model_id,
        "model_revision": config.model_revision,
        "dimension": config.dimension,
        "dtype": config.dtype,
        "normalized": config.normalized,
        "product_count": len(ids),
        "product_text_template": PRODUCT_TEXT_TEMPLATE,
        "query_text_template": QUERY_TEXT_TEMPLATE,
        "sentence_transformers_version": importlib.metadata.version("sentence-transformers"),
        "transformers_version": importlib.metadata.version("transformers"),
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
        "batch_size": args.batch_size,
        "seed": None,
        "build_seconds": round(build_seconds, 6),
        "vectors_bytes": vectors_path.stat().st_size,
        "ids_bytes": ids_path.stat().st_size,
        "ids_sha256": file_sha256(ids_path),
        "vectors_sha256": file_sha256(vectors_path),
        "approximate_vector_memory_bytes": int(vectors.nbytes),
        "platform": os.uname().sysname + "-" + os.uname().machine,
    }
    (cache_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
