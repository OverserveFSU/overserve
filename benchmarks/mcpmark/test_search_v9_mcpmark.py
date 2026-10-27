import unittest

from search_v9_mcpmark import select_candidate, validate_candidate


class ExperimentIntegrityTests(unittest.TestCase):
    def test_selection_requires_same_candidate_dual_fidelity(self):
        rows = [
            {"index": 0, "score": 999, "legacy_corner": True, "evaluation": {"audit_fid": True, "prod_fid": False}},
            {"index": 1, "score": 3, "legacy_corner": True, "evaluation": {"audit_fid": True, "prod_fid": True}},
            {"index": 2, "score": 3, "legacy_corner": True, "evaluation": {"audit_fid": True, "prod_fid": True}},
        ]
        self.assertIs(select_candidate(rows), rows[1])
        self.assertIsNone(select_candidate(rows[:1]))

    def test_failed_review_cannot_be_selected_for_transfer(self):
        rows = [{"index": 0, "score": 0, "legacy_corner": False,
                 "evaluation": {"audit_fid": True, "prod_fid": True}}]
        self.assertIsNone(select_candidate(rows))

    def test_handler_validation_before_execution(self):
        candidate = {"name": "status", "description": "Reports status.", "driver": "Confirm completion.",
                     "handler_src": "def handle(args, state, ds):\n r = ds.consistency_report()\n return {'complete': r.get('pending', 0) == 0}"}
        validate_candidate(candidate, {"read_file"})
        for source in ["import os\n" + candidate["handler_src"],
                       "def handle(args, state, ds):\n return open('/tmp/x').read()",
                       "def handle(args, state, ds):\n while True: pass",
                       "def handle(args, state, ds):\n return ds.__class__"]:
            with self.assertRaises(ValueError):
                validate_candidate({**candidate, "handler_src": source}, set())
        with self.assertRaises(ValueError):
            validate_candidate(candidate, {"status"})


if __name__ == "__main__":
    unittest.main()
