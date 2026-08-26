from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starter.retrieval.reranker import RerankerConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cache and validate the exact B5 CrossEncoder revision."
    )
    parser.add_argument("--output", default="docs/b5_reranker_cache.json")
    parser.add_argument("--model-cache-dir", default="models/huggingface/hub")
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Allow the pinned model revision to be downloaded into the local cache.",
    )
    args = parser.parse_args()

    config = RerankerConfig(model_cache_dir=Path(args.model_cache_dir))
    started = time.perf_counter()
    snapshot_path = Path(
        snapshot_download(
            repo_id=config.model_id,
            revision=config.model_revision,
            cache_dir=config.model_cache_dir,
            local_files_only=not args.allow_model_download,
            allow_patterns=[
                "config.json",
                "model.safetensors",
                "special_tokens_map.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt",
            ],
        )
    )

    from sentence_transformers import CrossEncoder

    model = CrossEncoder(
        config.model_id,
        revision=config.model_revision,
        cache_folder=str(config.model_cache_dir),
        local_files_only=True,
        max_length=config.max_length,
    )
    smoke_score = float(model.predict([("trail shoes", "comfortable trail shoes")])[0])
    files = [path for path in snapshot_path.rglob("*") if path.is_file()]
    try:
        recorded_snapshot_path = str(snapshot_path.relative_to(ROOT))
    except ValueError:
        recorded_snapshot_path = f"<external-cache>/{snapshot_path.name}"
    payload = {
        "model_id": config.model_id,
        "model_revision": config.model_revision,
        "model_cache_dir": str(config.model_cache_dir),
        "snapshot_path": recorded_snapshot_path,
        "snapshot_size_bytes": sum(path.stat().st_size for path in files),
        "snapshot_file_count": len(files),
        "candidate_limit": config.candidate_limit,
        "batch_size": config.batch_size,
        "max_length": config.max_length,
        "timeout_ms": config.timeout_ms,
        "runtime_network_access": False,
        "download_allow_patterns": [
            "config.json",
            "model.safetensors",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.txt",
        ],
        "cache_seconds": round(time.perf_counter() - started, 6),
        "validation": {
            "local_files_only": True,
            "smoke_score_is_finite": smoke_score == smoke_score,
        },
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
