"""Build/check an allowlisted source-only submission; no downloads or API calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULES = (
    "__init__.py", "agent.py", "contracts.py", "delivery.py",
    "core/__init__.py", "core/clarification.py", "core/context_engine.py",
    "core/decision_evidence.py", "core/diagnostics.py", "core/planner.py",
    "core/query_builder.py", "core/ranking.py", "core/response_guard.py", "core/state.py",
    "retrieval/__init__.py", "retrieval/conditional_dense.py", "retrieval/dense.py",
    "retrieval/fusion.py", "retrieval/hybrid.py", "retrieval/product_reranker.py",
    "retrieval/reranker.py", "retrieval/semantic_ranker.py", "retrieval/structured.py",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def contents():
    files = {}
    sources = {}

    def include(source, destination, prefix=b""):
        path = ROOT / source
        if path.is_symlink():
            raise ValueError(f"source symlinks are not allowed: {source}")
        data = path.read_bytes()
        sources[source] = digest(data)
        files[destination] = prefix + data

    for name in RUNTIME_MODULES:
        relative = "starter/" + name
        include(relative, "src/" + relative)
    for name in ("agent.py", "README.md", "REPORT.md", "THIRD_PARTY_NOTICES.md"):
        include("packaging/" + name, name)
    for name in ("requirements.txt", "requirements-dense.txt"):
        include(name, name)
    include("docs/delivery_configuration.md", "CONFIGURATION.md")
    include("docs/public_split_v1.json", "evaluation/public_split_v1.json")
    include("docs/development_folds_v1.json", "evaluation/development_folds_v1.json")
    # Keep __future__ first and then bootstrap the bundled helper import path.
    source = "scripts/build_dense_index.py"
    data = (ROOT / source).read_bytes()
    sources[source] = digest(data)
    bootstrap = b'\nimport sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))\n'
    files["tools/build_dense_index.py"] = data.replace(
        b"from __future__ import annotations\n", b"from __future__ import annotations\n" + bootstrap, 1)
    include("packaging/evaluate_offline.py", "tools/evaluate_offline.py")
    include("packaging/evaluate_final_public.py", "tools/evaluate_final_public.py")
    provenance = {"source_files_sha256": sources,
                  "offline_lineage": "3b0141633f2df8044fcbde4e9f99794f30778e93",
                  "f2_lineage": "a9e34ae4b125c8103b4f740134d7f1752a97c476",
                  "builder_sha256": digest(Path(__file__).read_bytes())}
    files["PROVENANCE.json"] = (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode()
    manifest = {name: digest(data) for name, data in sorted(files.items())}
    files["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "submission")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--archive", type=Path, help="Write a new deterministic source ZIP")
    args = parser.parse_args()
    target = args.output.absolute()
    if target.is_symlink() or target.resolve() == ROOT or target.resolve() in ROOT.parents:
        parser.error("output must be a dedicated bundle directory")
    files = contents()
    if target.exists():
        for path in target.rglob("*"):
            if path.is_symlink():
                parser.error("bundle contains symlinks")
            if path.is_file() and path.relative_to(target).as_posix() not in files:
                parser.error("bundle contains undeclared files; use a fresh output directory")
    for name, data in files.items():
        path = target / name
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                parser.error(f"stale or missing bundle file: {name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if args.archive:
        with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo("submission/" + name, date_time=(2026, 8, 31, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
    print(json.dumps({"status": "verified" if args.check else "built", "files": len(files)}))


if __name__ == "__main__":
    main()
