from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from experiments.a13_annotation_pack import load_jsonl, validate_items
from experiments.a13_annotation_trigger_audit import (
    validate_runtime_trigger_assignments,
)


BUNDLE_NAME = "a13_annotation_pack_v1"
PACK_FILES = (
    "README.md",
    "annotation_examples.md",
    "标注示例.html",
    "annotation_schema.json",
    "annotations.template.jsonl",
    "items.jsonl",
    "validate_annotations.py",
)
ANNOTATION_PAGE_TEMPLATE = "annotation_app.template.html"
ANNOTATION_PAGE_NAME = "开始标注.html"


def build_annotation_bundle(
    repository_root: str | Path,
    output_path: str | Path,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    source = root / "experiments/fixtures" / BUNDLE_NAME
    output = Path(output_path).resolve()
    items = load_jsonl(source / "items.jsonl")
    item_summary = validate_items(items)
    trigger_audit = validate_runtime_trigger_assignments(
        items,
        root / "data/catalog.jsonl",
    )
    if trigger_audit["mismatches"]:
        raise ValueError("A13 annotation items do not reproduce their runtime triggers")

    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory) / BUNDLE_NAME
        bundle.mkdir()
        for filename in PACK_FILES:
            shutil.copy2(source / filename, bundle / filename)
        annotation_page = (source / ANNOTATION_PAGE_TEMPLATE).read_text(
            encoding="utf-8"
        ).replace(
            "__A13_ITEMS_JSON__",
            json.dumps(items, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c")
            .replace(">", "\\u003e"),
        )
        (bundle / ANNOTATION_PAGE_NAME).write_text(
            annotation_page,
            encoding="utf-8",
        )
        shutil.copy2(
            root / "experiments/a13_annotation_pack.py",
            bundle / "a13_annotation_pack.py",
        )
        file_hashes = {
            path.name: _sha256(path)
            for path in sorted(bundle.iterdir(), key=lambda item: item.name)
        }
        manifest = {
            "version": "a13-annotation-pack-v1",
            "status": "annotation_ready_not_gold_frozen",
            **item_summary,
            "runtime_trigger_audit": trigger_audit,
            "files_sha256": file_hashes,
            "boundaries": {
                "contains_gold_labels": False,
                "contains_comparator_output": False,
                "contains_model_output": False,
                "contains_target_or_recommendations": False,
                "safe_for_independent_annotation": True,
            },
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_deterministic_zip(bundle, output)

    return {
        **manifest,
        "output": str(output),
        "zip_sha256": _sha256(output),
    }


def _write_deterministic_zip(bundle: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(bundle.iterdir(), key=lambda item: item.name):
            info = zipfile.ZipInfo(
                f"{BUNDLE_NAME}/{path.name}",
                date_time=(2026, 8, 29, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the standalone A13 annotation zip.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(
        json.dumps(
            build_annotation_bundle(root, args.output),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
