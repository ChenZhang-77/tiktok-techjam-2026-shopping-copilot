from __future__ import annotations

import json
import unittest

from experiments.failure_taxonomy import (
    CAUSE_ORDER,
    audit_session,
    build_report,
    classify_miss,
    summarize_failures,
    target_recall_summary,
    render_markdown,
)
from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalRequest, RetrievalResult
from starter.core.planner import Strategy


class FailureTaxonomyTest(unittest.TestCase):
    def _request(self, *, turn: int = 3, query: str = "red blue") -> RetrievalRequest:
        return RetrievalRequest(
            session_id="runtime-session",
            turn=turn,
            top_k=10,
            query=query,
            intent="buying",
            strategy=Strategy(
                intent="buying",
                lexical_weight=0.72,
                structured_weight=0.28,
                semantic_weight=0.0,
                retrieval_depth=80,
                allow_hard_filter=True,
                clarification_enabled=True,
                fallback_mode="lexical",
                reason="fixture",
            ),
        )

    def test_target_in_candidate_pool_below_top_ten_is_a_ranking_failure(self) -> None:
        classification = classify_miss(
            [
                {
                    "turn": 1,
                    "eligible": True,
                    "retrieval_depth": 80,
                    "target_lexical_rank": 18,
                    "target_final_rank": 14,
                    "intent": "buying",
                    "ask_attribute": "material",
                    "unproductive_reply": False,
                    "state_flags": [],
                    "missing_disclosed_values": 0,
                }
            ]
        )

        self.assertEqual(classification["primary_cause"], "ranking_filtering")
        self.assertEqual(classification["best_lexical_rank"], 18)
        self.assertEqual(classification["best_final_rank"], 14)
        self.assertEqual(classification["secondary_causes"], [])

    def test_observable_stale_or_unstable_state_takes_precedence(self) -> None:
        classification = classify_miss(
            [
                {
                    "turn": 3,
                    "eligible": True,
                    "retrieval_depth": 100,
                    "target_lexical_rank": None,
                    "target_final_rank": None,
                    "intent": "browsing",
                    "ask_attribute": "feature",
                    "unproductive_reply": False,
                    "state_flags": ["override_old_value_still_active"],
                    "missing_disclosed_values": 0,
                }
            ]
        )

        self.assertEqual(classification["primary_cause"], "state_override")
        self.assertEqual(classification["secondary_causes"], ["retrieval_recall"])
        self.assertEqual(
            classification["state_flags"],
            ["override_old_value_still_active"],
        )

    def test_missing_disclosed_evidence_is_an_extraction_failure(self) -> None:
        classification = classify_miss(
            [
                {
                    "turn": 2,
                    "eligible": True,
                    "retrieval_depth": 120,
                    "target_lexical_rank": None,
                    "target_final_rank": None,
                    "intent": "browsing",
                    "ask_attribute": "color",
                    "unproductive_reply": False,
                    "state_flags": [],
                    "missing_disclosed_values": 2,
                }
            ]
        )

        self.assertEqual(classification["primary_cause"], "extraction")
        self.assertEqual(classification["secondary_causes"], ["retrieval_recall"])
        self.assertEqual(classification["missing_disclosed_value_count"], 2)

    def test_repeated_unproductive_replies_are_a_question_policy_failure(self) -> None:
        turns = [
            {
                "turn": turn,
                "eligible": True,
                "retrieval_depth": 120,
                "target_lexical_rank": None,
                "target_final_rank": None,
                "intent": "browsing",
                "ask_attribute": "feature" if turn == 1 else "brand",
                "unproductive_reply": turn in {2, 3},
                "state_flags": [],
                "missing_disclosed_values": 0,
            }
            for turn in range(1, 4)
        ]

        classification = classify_miss(turns)

        self.assertEqual(classification["primary_cause"], "question_policy")
        self.assertEqual(classification["secondary_causes"], ["retrieval_recall"])
        self.assertEqual(classification["unproductive_reply_count"], 2)

    def test_query_construction_is_distinct_from_extraction(self) -> None:
        classification = classify_miss(
            [
                {
                    "turn": 2,
                    "eligible": True,
                    "target_lexical_rank": None,
                    "target_final_rank": None,
                    "extraction_flags": [],
                    "query_construction_flags": ["active_value_missing_from_query:leather"],
                }
            ]
        )

        self.assertEqual(classification["primary_cause"], "query_construction")
        self.assertEqual(classification["secondary_causes"], ["retrieval_recall"])

    def test_intent_strategy_routing_has_its_own_causal_stage(self) -> None:
        classification = classify_miss(
            [
                {
                    "turn": 3,
                    "eligible": True,
                    "target_lexical_rank": 21,
                    "target_final_rank": 18,
                    "intent_strategy_flags": ["buying_to_browsing_without_exploration"],
                }
            ]
        )

        self.assertEqual(classification["primary_cause"], "intent_strategy_routing")
        self.assertEqual(classification["secondary_causes"], ["ranking_filtering"])

    def test_response_contract_precedes_downstream_ranking_only_when_observed(self) -> None:
        classification = classify_miss(
            [
                {
                    "turn": 1,
                    "eligible": True,
                    "target_lexical_rank": 1,
                    "target_final_rank": 1,
                    "response_contract_flags": ["retrieved_top_k_target_missing_from_response"],
                }
            ]
        )

        self.assertEqual(classification["primary_cause"], "response_contract")
        self.assertEqual(classification["secondary_causes"], [])

    def test_evaluation_validity_flags_do_not_become_behavior_causes(self) -> None:
        classification = classify_miss(
            [
                {
                    "turn": 1,
                    "eligible": True,
                    "target_lexical_rank": None,
                    "target_final_rank": None,
                    "evaluation_validity_flags": ["missing_retrieval_trace"],
                }
            ]
        )

        self.assertEqual(classification["primary_cause"], "retrieval_recall")
        self.assertEqual(
            classification["evaluation_validity_flags"],
            ["missing_retrieval_trace"],
        )

    def test_summary_separates_control_and_retrieval_causes(self) -> None:
        summary = summarize_failures(
            [
                {"sample_id": "s1", "scenario_type": "buying", "primary_cause": "state_override"},
                {"sample_id": "s2", "scenario_type": "buying", "primary_cause": "ranking_filtering"},
                {"sample_id": "s3", "scenario_type": "browsing", "primary_cause": "retrieval_recall"},
            ]
        )

        self.assertEqual(
            summary["primary_cause_counts"],
            {"ranking_filtering": 1, "retrieval_recall": 1, "state_override": 1},
        )
        self.assertEqual(summary["owner_counts"], {"control_plane": 1, "retrieval_ranking": 2})
        self.assertEqual(
            summary["by_scenario"]["buying"],
            {"ranking_filtering": 1, "state_override": 1},
        )
        self.assertEqual(
            CAUSE_ORDER,
            (
                "extraction",
                "state_override",
                "intent_strategy_routing",
                "query_construction",
                "question_policy",
                "retrieval_recall",
                "ranking_filtering",
                "response_contract",
            ),
        )

    def test_target_recall_reports_observed_depth_coverage(self) -> None:
        sessions = [
            {"turns": [{"eligible": True, "retrieval_depth": 80, "target_lexical_rank": 8}]},
            {"turns": [{"eligible": True, "retrieval_depth": 80, "target_lexical_rank": 45}]},
            {"turns": [{"eligible": True, "retrieval_depth": 60, "target_lexical_rank": None}]},
        ]

        recall = target_recall_summary(sessions, depths=(10, 60, 80))

        self.assertEqual(recall["retained_depth"], {"hits": 2, "sessions": 3, "recall": 0.666667})
        self.assertEqual(recall["at_10"], {"hits": 1, "sessions": 3, "recall": 0.333333})
        self.assertEqual(recall["at_60"], {"hits": 2, "sessions": 3, "recall": 0.666667})
        self.assertEqual(recall["at_80"], {"hits": 2, "sessions": 2, "recall": 1.0})

    def test_session_audit_keeps_target_offline_and_detects_stale_override_state(self) -> None:
        request = self._request()
        result = RetrievalResult(
            candidates=[
                Candidate(
                    parent_asin="TARGET",
                    diagnostics={"lexical_rank": 15, "final_rank": 12},
                )
            ],
            diagnostics=RetrievalDiagnostics(route="structured", candidate_count=1),
        )
        audit = audit_session(
            sample={
                "sample_id": "public_fixture",
                "scenario_type": "intent_override",
                "ground_truth": {"parent_asin": "TARGET"},
            },
            evaluation_session={"hit": False, "first_hit_turn": None, "best_rank": None},
            intent_card={"hard_constraints": ["blue"], "soft_preferences": []},
            behavior={
                "override": {"turn": 3, "old_value": "red", "new_value": "blue"}
            },
            response_turns=[
                {
                    "turn": 3,
                    "user_message": "Actually, what I need is blue.",
                    "response": {
                        "ask_attribute": "feature",
                        "diagnostics": {
                            "intent": "buying",
                            "active_constraints": [
                                {"attribute": "color", "value": "red"},
                                {"attribute": "color", "value": "blue"},
                            ],
                            "rejected_constraints": [],
                            "no_preference_attributes": [],
                            "distilled_query": "red blue",
                        },
                    },
                }
            ],
            retrieval_turns={3: {"request": request, "result": result}},
        )

        self.assertEqual(audit["classification"]["primary_cause"], "state_override")
        self.assertEqual(audit["turns"][0]["target_final_rank"], 12)
        self.assertNotIn("TARGET", json.dumps(audit))

    def test_session_audit_separates_extracted_value_from_query_omission(self) -> None:
        request = self._request(turn=1, query="black")
        result = RetrievalResult(
            candidates=[],
            diagnostics=RetrievalDiagnostics(route="structured", candidate_count=0),
        )

        audit = audit_session(
            sample={
                "sample_id": "query_fixture",
                "scenario_type": "buying",
                "ground_truth": {"parent_asin": "TARGET"},
            },
            evaluation_session={"hit": False, "first_hit_turn": None, "best_rank": None},
            intent_card={"hard_constraints": ["black"], "soft_preferences": ["leather"]},
            behavior={},
            response_turns=[
                {
                    "turn": 1,
                    "user_message": "I need black leather shoes.",
                    "response": {
                        "ask_attribute": "size",
                        "recommendations": [],
                        "diagnostics": {
                            "intent": "buying",
                            "active_constraints": [
                                {"attribute": "color", "value": "black"},
                                {"attribute": "material", "value": "leather"},
                            ],
                            "rejected_constraints": [],
                            "overridden_constraints": [],
                            "no_preference_attributes": [],
                            "distilled_query": "black",
                        },
                    },
                }
            ],
            retrieval_turns={1: {"request": request, "result": result}},
        )

        turn = audit["turns"][0]
        self.assertEqual(turn["extraction_flags"], [])
        self.assertEqual(
            turn["query_construction_flags"],
            ["active_value_missing_from_query:leather"],
        )
        self.assertEqual(audit["classification"]["primary_cause"], "query_construction")

    def test_report_recommends_upstream_work_when_control_failures_dominate(self) -> None:
        base_turn = {
            "turn": 1,
            "eligible": True,
            "retrieval_depth": 80,
            "target_lexical_rank": None,
            "target_final_rank": None,
        }
        audits = [
            {
                "sample_id": "hit",
                "scenario_type": "buying",
                "hit": True,
                "first_hit_turn": 1,
                "best_rank": 1,
                "turns": [{**base_turn, "target_lexical_rank": 1, "target_final_rank": 1}],
            },
            {
                "sample_id": "state-miss",
                "scenario_type": "intent_override",
                "hit": False,
                "first_hit_turn": None,
                "best_rank": None,
                "turns": [base_turn],
                "classification": {
                    "primary_cause": "state_override",
                    "secondary_causes": ["retrieval_recall"],
                },
            },
            {
                "sample_id": "extract-miss",
                "scenario_type": "browsing",
                "hit": False,
                "first_hit_turn": None,
                "best_rank": None,
                "turns": [base_turn],
                "classification": {
                    "primary_cause": "extraction",
                    "secondary_causes": ["retrieval_recall"],
                    "evidence": {
                        "extraction": ["disclosed_value_not_extracted:leather"]
                    },
                },
            },
        ]

        report = build_report(
            audits,
            provenance={"commit": "abc1234", "worktree_clean": True},
            fold_manifest={
                "version": "fixture-folds-v1",
                "folds": {
                    "fold_1": ["hit", "state-miss"],
                    "fold_2": ["extract-miss"],
                },
            },
        )

        self.assertEqual(report["sample_count"], 3)
        self.assertEqual(report["miss_count"], 2)
        self.assertEqual(report["failure_summary"]["owner_counts"]["control_plane"], 2)
        self.assertEqual(report["next_experiment"]["id"], "A8")

        markdown = render_markdown(report)
        self.assertEqual(report["version"], "r0-v2")
        self.assertEqual(
            report["fold_summary"]["fold_1"],
            {
                "sample_count": 2,
                "hit_count": 1,
                "miss_count": 1,
                "primary_cause_counts": {"state_override": 1},
            },
        )
        self.assertEqual(report["fold_manifest_version"], "fixture-folds-v1")
        self.assertIn("# R0 Development Failure Taxonomy", markdown)
        self.assertIn("| state_override | 1 |", markdown)
        self.assertIn("**A8**", markdown)
        self.assertIn("offline-only", markdown)
        self.assertIn(
            "extract-miss (disclosed_value_not_extracted:leather)",
            markdown,
        )


if __name__ == "__main__":
    unittest.main()
