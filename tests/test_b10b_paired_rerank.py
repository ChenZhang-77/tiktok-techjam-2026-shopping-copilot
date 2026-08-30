import unittest
from dataclasses import replace
from starter.contracts import RetrievalDiagnostics

from experiments.b10b_paired_rerank import ObservedRetriever
from tests.test_b10b_full_rerank import BaseRetriever, request


class PairedRerankTest(unittest.TestCase):
    def test_observer_retains_fallback_but_excludes_measured_latency_from_digest(self):
        class DiagnosticSource(BaseRetriever):
            diagnostic = RetrievalDiagnostics(route="fixture", candidate_count=4, latency_ms=1)
            def retrieve(self, request):
                return replace(super().retrieve(request), diagnostics=self.diagnostic)
        base = DiagnosticSource()
        observer = ObservedRetriever(base)
        observer.retrieve(request())
        base.diagnostic = replace(base.diagnostic, latency_ms=9, stage_latencies_ms={"dense": 8})
        observer.retrieve(request())
        self.assertEqual(observer.records[0]["result_sha256"], observer.records[1]["result_sha256"])
        base.diagnostic = replace(base.diagnostic, fallback_used=True, route_failures={"dense": "synthetic_failure"})
        result = observer.retrieve(request())
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertNotEqual(observer.records[1]["result_sha256"], observer.records[2]["result_sha256"])
        self.assertEqual(observer.records[2]["route_failures"], {"dense": "synthetic_failure"})

    def test_observer_preserves_results_and_ignores_only_session_identity(self):
        base = BaseRetriever()
        observer = ObservedRetriever(base)
        original = request()
        result = observer.retrieve(original)
        self.assertEqual(result, base.retrieve(original))
        observer.retrieve(replace(original, session_id="different"))
        observer.retrieve(replace(original, query="a different query"))
        self.assertEqual(observer.records[0]["request_sha256"], observer.records[1]["request_sha256"])
        self.assertNotEqual(observer.records[0]["request_sha256"], observer.records[2]["request_sha256"])
        self.assertEqual(observer.records[0]["result_sha256"], observer.records[1]["result_sha256"])


if __name__ == "__main__":
    unittest.main()
