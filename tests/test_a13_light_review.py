import unittest
import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

from experiments.a13_light_review import cases, main, provider_input, score


class LightReviewTest(unittest.TestCase):
    def test_expected_synthetic_effects_pass_real_validator(self):
        for case in cases():
            with self.subTest(message=case["message"]):
                self.assertTrue(score(case, case["expected"])["exact"])

    def test_provider_input_excludes_expected_answer_and_case_metadata(self):
        case = dict(cases()[0], target_asin="SECRET", scenario_type="SECRET")
        self.assertEqual(set(provider_input(case)), {
            "current_message", "prior_state", "allowed_values", "override_detected"
        })

    def test_invalid_or_wrong_polarity_does_not_count_as_correct(self):
        case = cases()[0]
        self.assertFalse(score(case, {"intent_hint": []})["exact"])
        wrong = dict(case["expected"], positive_constraints=[],
                     rejected_constraints=case["expected"]["positive_constraints"])
        self.assertFalse(score(case, wrong)["exact"])

    def test_malformed_provider_response_saves_inconclusive_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "result.json"
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b'{"choices":[]}'
            with patch("sys.argv", ["lr0", "--allow-provider", "--output", str(output)]), \
                 patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-key"}), \
                 patch("urllib.request.OpenerDirector.open", return_value=response), \
                 contextlib.redirect_stdout(io.StringIO()):
                main()
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "provider_failure_inconclusive")
            self.assertEqual(report["completed_pairs"], 0)
            self.assertEqual(report["attempted_calls"], 1)

    def test_unwritable_output_target_fails_before_provider_access(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "not-a-directory"
            parent.touch()
            with patch("sys.argv", ["lr0", "--allow-provider", "--output", str(parent / "r.json")]), \
                 patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-key"}), \
                 patch("urllib.request.OpenerDirector.open") as network:
                with self.assertRaises(OSError):
                    main()
                network.assert_not_called()
