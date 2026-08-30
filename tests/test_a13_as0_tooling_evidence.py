from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from experiments.a13_ai_silver import (
    build_as0_preflight_report,
    build_role_artifact_bindings,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "experiments/fixtures/a13_ai_silver_v1"
EVIDENCE = ROOT / "docs/a13_as0_offline_tooling_evidence.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class A13AS0ToolingEvidenceTest(unittest.TestCase):
    def test_pending_role_manifest_binds_known_fields_but_does_not_authorize(self) -> None:
        path = CONTRACT / "role_manifest.pending.json"
        pending = json.loads(path.read_text(encoding="utf-8"))
        bindings = build_role_artifact_bindings(CONTRACT)
        roles = [
            pending["candidate"],
            pending["generator"],
            pending["duplicate_auditor"],
            *pending["labelers"],
            pending["adjudicator"],
        ]
        for role in roles:
            for field, digest in bindings[role["role"]].items():
                self.assertEqual(role[field], digest)
        self.assertEqual(pending["candidate"]["provider"], "deepseek")
        self.assertEqual(
            pending["candidate"]["model_version"], "DeepSeek-V4-Flash-0731"
        )
        report = build_as0_preflight_report(CONTRACT, path)
        self.assertEqual(report["status"], "blocked_role_manifest")
        self.assertEqual(report["role_manifest_error"], "invalid generator provider")
        self.assertFalse(report["reference_builder_provider_authorized"])
        self.assertFalse(report["execution_runner_ready"])

    def test_evidence_binds_offline_contracts_and_the_provider_blocker(self) -> None:
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        preflight = build_as0_preflight_report(
            CONTRACT,
            CONTRACT / "role_manifest.template.json",
        )

        self.assertEqual(evidence["version"], "a13-as0-offline-tooling-v1")
        self.assertEqual(evidence["decision"], "offline_core_contracts_passed")
        self.assertEqual(evidence["phase_status"], "blocked_roles_and_runner")
        self.assertEqual(evidence["artifact_sha256"], preflight["artifact_sha256"])
        self.assertEqual(
            evidence["code_sha256"],
            {
                "experiments/a13_ai_silver.py": _sha256(
                    ROOT / "experiments/a13_ai_silver.py"
                ),
                "tests/test_a13_ai_silver.py": _sha256(
                    ROOT / "tests/test_a13_ai_silver.py"
                ),
            },
        )
        self.assertEqual(evidence["boundaries"]["provider_calls"], 0)
        self.assertFalse(
            evidence["boundaries"]["reference_builder_provider_authorized"]
        )
        self.assertFalse(evidence["boundaries"]["candidate_provider_authorized"])
        self.assertFalse(evidence["boundaries"]["execution_runner_ready"])
        self.assertFalse(preflight["execution_runner_ready"])
        self.assertFalse(evidence["boundaries"]["runtime_changed"])
        self.assertFalse(evidence["boundaries"]["legacy_fixture_reused"])


if __name__ == "__main__":
    unittest.main()
