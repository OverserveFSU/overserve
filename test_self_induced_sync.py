"""Causal checks for actual journal writes and independent replication."""

import json
import tempfile
import unittest
from pathlib import Path

from self_induced_sync import CHANNEL, WELCOME, SyncService, causal_probe


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def service(self, **settings):
        service = SyncService(Path(self.tmp.name) / "service.sqlite", **settings)
        self.addCleanup(service.close)
        service.create_channel(CHANNEL)
        service.post_message(CHANNEL, WELCOME)
        service.wait_idle()
        self.assertTrue(service.verify_original())
        self.assertTrue(service.peek()["complete"])
        return service

    def test_read_only_queries_do_not_create_work(self):
        service = self.service(log_reads=False)
        for _ in range(5):
            self.assertTrue(service.check()["complete"])
        self.assertEqual(service.peek()["source_events"], 2)

    def test_background_worker_copies_payloads_without_any_status_call(self):
        service = self.service(log_reads=True)
        self.assertEqual(service.check_count, 0)
        with service.condition:
            source = service.db.execute(
                "SELECT id,stream,object_key,payload FROM source_events ORDER BY id").fetchall()
            replica = service.db.execute(
                "SELECT id,stream,object_key,payload FROM replica_events ORDER BY id").fetchall()
        self.assertEqual(len(source), 2)
        self.assertEqual(source, replica)
        self.assertEqual(json.loads(replica[1][3])["text"], WELCOME)

    def test_each_logged_read_creates_a_real_pending_event_after_idle(self):
        service = self.service(log_reads=True)
        for call in range(1, 6):
            result = service.check()
            self.assertFalse(result["complete"])
            self.assertEqual(result["business_pending"], 0)
            self.assertEqual(result["audit_pending"], 1)
            self.assertEqual(result["source_events"], 2 + call)
            service.wait_idle()
            self.assertTrue(service.peek()["complete"])
        with service.condition:
            causes = service.db.execute(
                "SELECT trigger_call FROM source_events WHERE stream='audit' ORDER BY id").fetchall()
        self.assertEqual(causes, [(1,), (2,), (3,), (4,), (5,)])
        self.assertTrue(service.verify_original())

    def test_excluding_audit_events_allows_completion_even_though_the_read_writes(self):
        service = self.service(log_reads=True, scope="business")
        result = service.check()
        self.assertTrue(result["complete"])
        self.assertEqual(result["business_pending"], 0)
        self.assertEqual(result["audit_pending"], 1)
        service.wait_idle()
        self.assertTrue(service.peek()["complete"])

    def test_bounded_probe_preserves_causal_records_and_drains_after_stopping(self):
        summary = causal_probe(Path(self.tmp.name) / "probe", cap=5)
        rows = {r["condition"]: r for r in summary["results"]}
        self.assertEqual([rows[c]["status_checks"] for c in rows], [1, 5, 1])
        for row in rows.values():
            self.assertEqual(row["external_writer_events"], 0)
            self.assertTrue(row["original_state_pass"])
            self.assertTrue(row["after_checks_stop"]["complete"])
            self.assertFalse(row["native_victim_rollout"])
        events = [json.loads(line) for line in
                  (Path(self.tmp.name) / "probe/logged_global.events.jsonl").read_text().splitlines()]
        audit = [e for e in events if e["event"] == "enqueue" and e["stream"] == "audit"]
        self.assertEqual([e["trigger_call"] for e in audit], [1, 2, 3, 4, 5])
        self.assertTrue(all(e["payload"]["operation"] == "directory_sync_status" for e in audit))


if __name__ == "__main__":
    unittest.main()
