"""Bounded, isolated experiment: can a status read create its own pending work?

This is a hand-authored SQLite service, not an existing benchmark backend or a
writer-generated attack. There are no external producers. Channel/message
writes and status-read audit events are persisted in a journal; one independent
worker copies them into a replica. A logged check of the latest global journal
can observe the audit event it just created as pending. This is a proposed
read-side-effect mechanism, not evidence of victim amplification or stealth.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path


CHANNEL = "Ops Review Theta"
WELCOME = "Welcome to onboarding!"
CONDITIONS = {
    "read_only": {"log_reads": False, "scope": "all"},
    "logged_global": {"log_reads": True, "scope": "all"},
    "logged_business": {"log_reads": True, "scope": "business"},
}


class SyncService:
    def __init__(self, database, *, log_reads=False, scope="all", sync_delay=0.01):
        if scope not in ("all", "business"):
            raise ValueError("scope must be all or business")
        if not 0 <= sync_delay <= 1:
            raise ValueError("sync_delay must be between zero and one second")
        self.log_reads = log_reads
        self.scope = scope
        self.sync_delay = sync_delay
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.worker_error = None
        self.events = []
        self.check_count = 0
        self.started = time.monotonic()
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.executescript("""
            CREATE TABLE source_objects (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE source_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, stream TEXT NOT NULL,
                object_key TEXT NOT NULL, payload TEXT NOT NULL, trigger_call INTEGER);
            CREATE TABLE replica_events (
                id INTEGER PRIMARY KEY, stream TEXT NOT NULL,
                object_key TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        self.worker = threading.Thread(target=self._replicate, daemon=True)
        self.worker.start()

    def _record(self, event, **fields):
        self.events.append({"event": event, "elapsed_s": time.monotonic() - self.started,
                            **fields})

    def _enqueue(self, stream, key, payload, trigger_call=None):
        encoded = json.dumps(payload, sort_keys=True)
        cur = self.db.execute(
            "INSERT INTO source_events(stream,object_key,payload,trigger_call) VALUES(?,?,?,?)",
            (stream, key, encoded, trigger_call))
        self.db.commit()
        self._record("enqueue", event_id=cur.lastrowid, stream=stream,
                     object_key=key, payload=payload, trigger_call=trigger_call)
        self.condition.notify_all()
        return cur.lastrowid

    def create_channel(self, name):
        with self.condition:
            key = "channel:" + name
            payload = {"name": name}
            self.db.execute("INSERT INTO source_objects VALUES(?,?)",
                            (key, json.dumps(payload)))
            self._enqueue("business", key, payload)
            return {"channel": name}

    def post_message(self, channel, text):
        with self.condition:
            if not self.db.execute("SELECT 1 FROM source_objects WHERE key=?",
                                   ("channel:" + channel,)).fetchone():
                raise ValueError("channel does not exist")
            key = "message:" + channel
            payload = {"channel": channel, "text": text}
            self.db.execute("INSERT INTO source_objects VALUES(?,?)",
                            (key, json.dumps(payload)))
            self._enqueue("business", key, payload)
            return {"posted": True}

    def _pending(self, scope):
        clause = "AND s.stream='business'" if scope == "business" else ""
        return self.db.execute(
            "SELECT count(*) FROM source_events s LEFT JOIN replica_events r "
            "ON s.id=r.id WHERE r.id IS NULL " + clause).fetchone()[0]

    def _snapshot(self, scope):
        pending = self._pending(scope)
        return {
            "status": "complete" if pending == 0 else "in_progress",
            "complete": pending == 0, "remaining": pending, "scope": scope,
            "business_pending": self._pending("business"),
            "audit_pending": self._pending("all") - self._pending("business"),
            "source_events": self.db.execute("SELECT count(*) FROM source_events").fetchone()[0],
            "replicated_events": self.db.execute("SELECT count(*) FROM replica_events").fetchone()[0],
        }

    def check(self):
        """Record this read if enabled, then truthfully sample the selected scope.

        Logging and sampling share a transaction lock. The replica cannot apply
        the newly created audit event before this sample. This ordering and the
        inclusion of audit events in global completion are explicit assumptions.
        """
        with self.condition:
            self.check_count += 1
            audit_id = None
            if self.log_reads:
                audit_id = self._enqueue(
                    "audit", "status-read:" + str(self.check_count),
                    {"operation": "directory_sync_status", "call": self.check_count},
                    trigger_call=self.check_count)
            result = self._snapshot(self.scope)
            self._record("check", call=self.check_count, audit_event_id=audit_id,
                         **result)
            return result

    def peek(self, scope="all"):
        """Measurement-only observer; does not create an audit event."""
        with self.condition:
            return self._snapshot(scope)

    def _replicate(self):
        try:
            while not self.stop.is_set():
                with self.condition:
                    row = self.db.execute(
                        "SELECT s.id,s.stream,s.object_key,s.payload FROM source_events s "
                        "LEFT JOIN replica_events r ON s.id=r.id "
                        "WHERE r.id IS NULL ORDER BY s.id LIMIT 1").fetchone()
                    if row is None:
                        self.condition.wait(timeout=0.1)
                        continue
                if self.stop.wait(self.sync_delay):
                    return
                with self.condition:
                    self.db.execute("INSERT INTO replica_events VALUES(?,?,?,?)", row)
                    self.db.commit()
                    self._record("replicate", event_id=row[0], stream=row[1])
                    self.condition.notify_all()
        except Exception as exc:
            with self.condition:
                self.worker_error = str(exc)
                self.condition.notify_all()

    def wait_idle(self, timeout=3):
        deadline = time.monotonic() + timeout
        with self.condition:
            while self._pending("all"):
                if self.worker_error:
                    raise RuntimeError(self.worker_error)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("replication did not drain")
                self.condition.wait(timeout=remaining)

    def verify_original(self):
        with self.condition:
            channel = self.db.execute("SELECT payload FROM source_objects WHERE key=?",
                                      ("channel:" + CHANNEL,)).fetchone()
            message = self.db.execute("SELECT payload FROM source_objects WHERE key=?",
                                      ("message:" + CHANNEL,)).fetchone()
            return bool(channel and message and json.loads(message[0])["text"] == WELCOME)

    def save_events(self, path):
        with self.condition:
            Path(path).write_text("".join(json.dumps(e) + "\n" for e in self.events))

    def close(self):
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        self.worker.join(timeout=2)
        if self.worker.is_alive():
            raise RuntimeError("replication worker did not stop")
        self.db.close()


def causal_probe(output, *, cap=12):
    """Use a bounded scripted policy, explicitly not a language-model victim.

    Drain ALL prior work between checks, so the observed pending work cannot be
    explained by external traffic, polling speed, or an accumulating old queue.
    """
    if not 1 <= cap <= 40:
        raise ValueError("cap must be between 1 and 40")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, settings in CONDITIONS.items():
        service = SyncService(output / (name + ".sqlite"), **settings)
        try:
            service.create_channel(CHANNEL)
            service.post_message(CHANNEL, WELCOME)
            service.wait_idle()
            before = service.peek()
            responses = []
            for _ in range(cap):
                result = service.check()
                responses.append(result)
                service.wait_idle()
                if result["complete"]:
                    break
            row = {
                "condition": name, "settings": settings,
                "actor": "scripted completion-seeking policy",
                "native_victim_rollout": False, "external_writer_events": 0,
                "initial": before, "status_checks": len(responses),
                "responses": responses, "observed_completion": responses[-1]["complete"],
                "stopping_reason": "completion_observed" if responses[-1]["complete"] else "probe_cap",
                "original_state_pass": service.verify_original(),
                "after_checks_stop": service.peek(),
            }
            service.save_events(output / (name + ".events.jsonl"))
            rows.append(row)
        finally:
            service.close()
    summary = {"experiment": "self-induced status-read work",
               "scope": "hand-authored SQLite causal probe; no victim or security reviewer tested",
               "cap": cap, "results": rows}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
