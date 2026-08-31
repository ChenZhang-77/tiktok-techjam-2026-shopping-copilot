"""Exercise the bundle CLI and isolated public Agent import, never a provider."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class DeliveryPackageTest(unittest.TestCase):
    def test_archive_is_source_only_and_tampering_fails_check(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bundle"
            archive = Path(temp) / "submission.zip"
            command = [sys.executable, "scripts/build_submission.py", "--output", str(target)]
            subprocess.run(command + ["--archive", str(archive)], cwd=ROOT, check=True, capture_output=True)
            manifest = json.loads((target / "MANIFEST.json").read_text())
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), {"submission/" + n for n in manifest} | {"submission/MANIFEST.json"})
                self.assertFalse(any(".env" in n or "/evaluator/" in n for n in bundle.namelist()))
            (target / "agent.py").write_text("tampered")
            result = subprocess.run(command + ["--check"], cwd=ROOT, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_bundle_build_exports_agent_without_the_source_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bundle"
            subprocess.run([sys.executable, "scripts/build_submission.py", "--output", str(target)],
                           cwd=ROOT, check=True, capture_output=True)
            (target / "data").mkdir()
            (target / "data/catalog.jsonl").write_text("".join(json.dumps({
                "parent_asin": f"ITEM-{i}", "title": "walking shoes", "categories": ["Shoes"],
                "features": [], "details": {}, "description": [], "store": "Fixture",
            }) + "\n" for i in range(40)))
            code = '''
import json, sys, urllib.request
sys.path.insert(0, ".")
def forbidden(*args, **kwargs):
    raise AssertionError("network forbidden")
urllib.request.urlopen = forbidden
from agent import Agent
a = Agent()
a.reset("fresh", {})
r = a.respond("fresh", "Show me shoes", 1, 10)
print(json.dumps(r))
a.close()
'''
            env = {**os.environ, "SHOPPING_MODE": "offline", "PYTHONDONTWRITEBYTECODE": "1",
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
            for key in ("PYTHONPATH", "SHOPPING_CATALOG", "SHOPPING_DENSE_CACHE", "SHOPPING_MODEL_CACHE"):
                env.pop(key, None)
            result = subprocess.run([sys.executable, "-I", "-c", code], cwd=target,
                                    env=env, check=True, capture_output=True, text=True)
            response = json.loads(result.stdout)
            ids = [r["parent_asin"] for r in response["recommendations"]]
            self.assertEqual(len(set(ids)), 10)
            self.assertEqual(response["diagnostics"]["delivery"]["requested_mode"], "offline")
            self.assertTrue(response["diagnostics"]["fallback_used"])
            self.assertFalse(any(p.is_symlink() for p in target.rglob("*")))


if __name__ == "__main__":
    unittest.main()
