"""Freeze/run CLI boundary tests use synthetic files, never the real Full200 set."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FinalPublicReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        subprocess.run([sys.executable, "scripts/build_submission.py", "--output", str(self.bundle)],
                       cwd=ROOT, check=True, capture_output=True)
        kit = self.root / "kit"
        (kit / "data").mkdir(parents=True)
        (kit / "evaluator").mkdir()
        (kit / "data/public_set.jsonl").write_text("synthetic-not-public-data\n")
        (kit / "evaluator/__init__.py").write_text("raise RuntimeError('must not evaluate')\n")
        catalog = self.root / "catalog.jsonl"
        catalog.write_text("synthetic-not-a-catalog\n")
        cache = self.root / "vectors"
        cache.mkdir()
        for name in ("metadata.json", "ids.json", "vectors.npy"):
            (cache / name).write_text("synthetic")
        model = self.root / "model"
        model.mkdir()
        (model / "weights.bin").write_text("synthetic")
        self.freeze = self.root / "freeze.json"
        self.output = self.root / "report.json"
        self.command = [sys.executable, str(self.bundle / "tools/evaluate_final_public.py"),
            "--kit-root", str(kit), "--catalog", str(catalog), "--cache-dir", str(cache),
            "--model-cache-dir", str(model), "--freeze-file", str(self.freeze)]

    def invoke(self, *args):
        return subprocess.run(self.command + list(args), capture_output=True, text=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def test_freeze_records_offline_provenance_without_evaluating(self):
        result = self.invoke("--freeze-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        freeze = json.loads(self.freeze.read_text())
        self.assertEqual(freeze["configuration"]["mode"], "offline")
        self.assertIn("src/starter/delivery.py", freeze["bundle_files_sha256"])
        self.assertFalse(self.output.exists())
        self.assertNotEqual(self.invoke("--freeze-only").returncode, 0)

    def test_changed_runtime_is_rejected_before_public_run(self):
        self.assertEqual(self.invoke("--freeze-only").returncode, 0)
        (self.bundle / "agent.py").write_text("tampered")
        result = self.invoke("--output", str(self.output))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integrity", result.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.freeze) + ".started").exists())

    def test_started_freeze_cannot_be_reused_for_another_public_run(self):
        self.assertEqual(self.invoke("--freeze-only").returncode, 0)
        Path(str(self.freeze) + ".started").write_text("synthetic prior run\n")
        result = self.invoke("--output", str(self.output))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already started", result.stderr)
        self.assertFalse(self.output.exists())

    def test_real_official_import_preflight_rejects_empty_synthetic_population(self):
        kit = self.root / "kit"
        for path in (ROOT / "evaluator").glob("*.py"):
            shutil.copyfile(path, kit / "evaluator" / path.name)
        (kit / "data/public_set.jsonl").write_text("")
        self.assertEqual(self.invoke("--freeze-only").returncode, 0)
        result = self.invoke("--output", str(self.output))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly 200 unique public sessions", result.stderr)
        self.assertFalse(Path(str(self.freeze) + ".started").exists())
