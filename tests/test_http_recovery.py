"""Recovery checks using real Requests traffic against a loopback-only server."""

from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import bus_data
from bus_data import PollingWorker, StopState, fetch_bus_arrival


def arrival_payload(service_no):
    return {"Services": [{
        "ServiceNo": service_no,
        "NextBus": {
            "EstimatedArrival": "2099-01-01T12:00:00+08:00",
            "Type": "SD",
        },
    }]}


def response(payload=None, *, status=200, body=None, gate=None, received=None):
    if body is None:
        body = json.dumps(payload).encode("utf-8")
    return {
        "status": status, "body": body, "gate": gate, "received": received,
    }


class LocalApiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        stop = parse_qs(urlsplit(self.path).query).get("BusStopCode", [None])[0]
        with self.server.script_lock:
            script = self.server.scripts.get(stop)
            action = script.popleft() if script else response(status=500, body=b"unexpected request")
            self.server.calls.append(stop)
        if action["received"] is not None:
            action["received"].set()
        if action["gate"] is not None:
            # The test releases this gate after Requests raises ReadTimeout.
            # The finite fallback also protects cleanup if an assertion fails.
            action["gate"].wait(3)
        try:
            self.send_response(action["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(action["body"])))
            self.end_headers()
            self.wfile.write(action["body"])
        except (BrokenPipeError, ConnectionResetError):
            # Expected when the client has already timed out and disconnected.
            pass

    def log_message(self, *args):
        pass


class HttpRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.gates = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), LocalApiHandler)
        self.server.daemon_threads = False
        self.server.script_lock = threading.Lock()
        self.server.scripts = {}
        self.server.calls = []
        self.server_thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.01),
            name="test-local-bus-api",
        )
        self.server_thread.start()
        self.addCleanup(self.close_server)
        endpoint = "http://127.0.0.1:{}/BusArrival".format(self.server.server_port)
        self.api_url = patch.object(bus_data, "API_URL", endpoint)
        self.api_url.start()
        self.addCleanup(self.api_url.stop)

    def close_server(self):
        for gate in self.gates:
            gate.set()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        self.assertFalse(self.server_thread.is_alive())

    def worker(self, *, timeout=(0.1, 0.5), interval=30):
        def fetch(api_key, stop, **kwargs):
            return fetch_bus_arrival(api_key, stop, timeout=timeout, **kwargs)

        worker = PollingWorker("local-test-key", ("A", "B"), fetcher=fetch, interval=interval)

        def close_worker():
            for gate in self.gates:
                gate.set()
            worker.stop()
            if worker.thread is not None:
                worker.thread.join(timeout=2)
                self.assertFalse(worker.thread.is_alive())

        self.addCleanup(close_worker)
        return worker

    def poll_into(self, worker, states):
        worker.poll_once()
        updates = worker.drain()
        self.assertEqual([update.stop_index for update in updates], [0, 1])
        for update in updates:
            states[update.stop_index].apply(update)
        return updates

    def assert_recovery(self, failure, expected_error, *, timeout=(0.1, 0.5)):
        self.server.scripts = {
            "A": deque([
                response(arrival_payload("A1")), failure,
                response(arrival_payload("A3")),
            ]),
            "B": deque(response(arrival_payload("B" + str(cycle))) for cycle in (1, 2, 3)),
        }
        worker = self.worker(timeout=timeout)
        states = [StopState(), StopState()]
        self.poll_into(worker, states)
        last_good_services = states[0].services
        last_good_time = states[0].last_updated

        started = time.monotonic()
        with self.assertLogs("bus_data", level="WARNING") as logged:
            failed_updates = self.poll_into(worker, states)
        elapsed = time.monotonic() - started
        self.assertEqual(failed_updates[0].error, expected_error)
        self.assertIs(states[0].services, last_good_services)
        self.assertEqual(states[0].last_updated, last_good_time)
        self.assertTrue(states[0].is_stale(datetime.now(timezone.utc)))
        self.assertIn("STALE", states[0].status(datetime.now(timezone.utc)))
        self.assertEqual(states[1].services[0].service_no, "B2")
        self.assertIsNone(states[1].error)
        self.assertEqual(len(logged.records), 1)

        self.poll_into(worker, states)
        self.assertEqual(states[0].services[0].service_no, "A3")
        self.assertIsNone(states[0].error)
        self.assertFalse(states[0].is_stale(datetime.now(timezone.utc)))
        self.assertEqual(states[1].services[0].service_no, "B3")
        self.assertEqual(self.server.calls, ["A", "B"] * 3)
        return elapsed

    def test_http_500_preserves_snapshot_and_recovers_on_next_poll(self):
        self.assert_recovery(response(status=500, body=b"service unavailable"), "HTTP 500")

    def test_invalid_json_preserves_snapshot_and_recovers_on_next_poll(self):
        self.assert_recovery(response(body=b"this is not JSON"), "JSONDecodeError")

    def test_malformed_api_payload_preserves_snapshot_and_recovers_on_next_poll(self):
        self.assert_recovery(response({"Services": {"invalid": "array required"}}), "ValueError")

    def test_finite_read_timeout_allows_other_stop_and_next_poll_to_succeed(self):
        release = threading.Event()
        received = threading.Event()
        self.gates.append(release)
        failure = response(arrival_payload("too late"), gate=release, received=received)
        elapsed = self.assert_recovery(failure, "Request timed out", timeout=(0.1, 0.05))
        self.assertTrue(received.is_set())
        self.assertFalse(release.is_set(), "Request must time out before the server is released")
        self.assertLess(elapsed, 1.5, "Read timeout must bound the blocked stop's request")
        release.set()

    def test_background_loop_retries_after_http_failure_without_manual_restart(self):
        release_second_poll = threading.Event()
        second_poll_received = threading.Event()
        self.gates.append(release_second_poll)
        self.server.scripts = {
            "A": deque([
                response(status=500, body=b"retry later"),
                response(arrival_payload("A2"), gate=release_second_poll,
                         received=second_poll_received),
            ]),
            "B": deque([
                response(arrival_payload("B1")),
                response(arrival_payload("B2")),
            ]),
        }
        worker = self.worker(interval=0.01)
        with self.assertLogs("bus_data", level="WARNING"):
            worker.start()
            first_cycle = [worker.results.get(timeout=2), worker.results.get(timeout=2)]
            self.assertEqual([update.stop_index for update in first_cycle], [0, 1])
            self.assertEqual(first_cycle[0].error, "HTTP 500")
            self.assertEqual(first_cycle[1].services[0].service_no, "B1")
            self.assertTrue(second_poll_received.wait(2))
            self.assertTrue(worker.thread.is_alive())
            release_second_poll.set()
            second_cycle = [worker.results.get(timeout=2), worker.results.get(timeout=2)]
            worker.stop()
        self.assertEqual([update.stop_index for update in second_cycle], [0, 1])
        self.assertEqual(second_cycle[0].services[0].service_no, "A2")
        self.assertEqual(second_cycle[1].services[0].service_no, "B2")
        self.assertTrue(all(update.error is None for update in second_cycle))


if __name__ == "__main__":
    unittest.main()
