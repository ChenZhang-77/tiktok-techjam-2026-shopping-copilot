import unittest

from experiments.a13_light_review import cases, provider_input, score


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
