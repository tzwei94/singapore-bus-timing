import unittest
from datetime import datetime, timedelta, timezone

import requests

from bus_data import (
    Arrival, PollingWorker, StopState, StopUpdate,
    fetch_bus_arrival, parse_services,
)


NOW = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)


def payload():
    return {"Services": [{
        "ServiceNo": "12", "Operator": "SBST",
        "NextBus": {"EstimatedArrival": "2026-10-26T11:02:00+08:00", "Type": "SD"},
        "NextBus2": {"EstimatedArrival": "2026-10-26T11:08:00+08:00", "Type": "DD"},
        "NextBus3": {"EstimatedArrival": "", "Type": ""},
    }]}


class ParsingTests(unittest.TestCase):
    def test_invalid_arrival_does_not_remove_service_or_shift_next_bus_slots(self):
        data = payload()
        data["Services"][0]["NextBus"]["EstimatedArrival"] = "invalid"
        services = parse_services(data)
        self.assertEqual(services[0].service_no, "12")
        self.assertIsNone(services[0].arrivals[0])
        self.assertEqual(services[0].arrivals[1].minutes_at(NOW), 8)
        self.assertEqual(services[0].arrivals[1].bus_type, "DD")
        self.assertIsNone(services[0].arrivals[2])

    def test_valid_empty_response_is_distinct_from_broken_response(self):
        self.assertEqual(parse_services({"Services": []}), ())
        for broken in ({}, {"Services": None}, {"Services": {}}, []):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                parse_services(broken)

    def test_invalid_service_does_not_discard_other_valid_services(self):
        data = payload()
        data["Services"].insert(0, {"NextBus": {}})
        self.assertEqual([s.service_no for s in parse_services(data)], ["12"])
        with self.assertRaises(ValueError):
            parse_services({"Services": [{"NextBus": {}}]})

    def test_service_without_any_estimates_still_has_a_row(self):
        service = parse_services({"Services": [{"ServiceNo": "27"}]})[0]
        self.assertEqual(service.service_no, "27")
        self.assertEqual(service.arrivals, (None, None, None))

    def test_cached_arrivals_count_down_and_expire_instead_of_freezing(self):
        arrival = Arrival(NOW + timedelta(minutes=8), "DD")
        self.assertEqual(arrival.minutes_at(NOW), 8)
        self.assertEqual(arrival.minutes_at(NOW + timedelta(minutes=2)), 6)
        self.assertEqual(arrival.minutes_at(NOW + timedelta(minutes=8, seconds=20)), 0)
        self.assertIsNone(arrival.minutes_at(NOW + timedelta(minutes=9, seconds=1)))


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return payload()


class FakeSession:
    def __init__(self):
        self.options = None

    def get(self, url, **kwargs):
        self.options = kwargs
        return FakeResponse()

    def close(self):
        pass


class PollingTests(unittest.TestCase):
    def test_http_request_has_finite_connect_and_read_timeouts(self):
        session = FakeSession()
        result = fetch_bus_arrival("not-a-real-key", "00001", session=session)
        self.assertEqual(result[0].service_no, "12")
        self.assertEqual(session.options["timeout"], (3.05, 10))

    def test_one_stop_failure_preserves_its_snapshot_and_other_stop_recovers(self):
        calls = {"A": 0, "B": 0}

        def fetch(api_key, stop, **kwargs):
            calls[stop] += 1
            if stop == "A" and calls[stop] == 2:
                raise requests.ConnectionError("offline")
            data = payload()
            data["Services"][0]["ServiceNo"] = stop + str(calls[stop])
            return parse_services(data)

        worker = PollingWorker("key", ("A", "B"), fetcher=fetch)
        self.addCleanup(worker.stop)
        states = [StopState(), StopState()]
        for cycle in range(3):
            worker.poll_once()
            for update in worker.drain():
                states[update.stop_index].apply(update)
            if cycle == 1:
                self.assertEqual(states[0].services[0].service_no, "A1")
                self.assertTrue(states[0].error)
                self.assertEqual(states[1].services[0].service_no, "B2")
        self.assertEqual(states[0].services[0].service_no, "A3")
        self.assertIsNone(states[0].error)
        self.assertEqual(states[1].services[0].service_no, "B3")

    def test_result_buffer_stays_bounded_when_ui_does_not_drain(self):
        worker = PollingWorker("key", ("A", "B"), fetcher=lambda *a, **k: ())
        self.addCleanup(worker.stop)
        for _ in range(100):
            worker.poll_once()
        updates = worker.drain()
        self.assertEqual(len(updates), 2)
        self.assertEqual({u.stop_index for u in updates}, {0, 1})


class StateTests(unittest.TestCase):
    def test_malformed_slot_keeps_previous_estimate_until_valid_recovery(self):
        state = StopState()
        state.apply(StopUpdate(0, parse_services(payload()), NOW))
        partial = payload()
        partial["Services"][0]["NextBus"]["EstimatedArrival"] = "invalid"
        partial["Services"][0]["NextBus2"]["EstimatedArrival"] = "2026-10-26T11:09:00+08:00"
        state.apply(StopUpdate(0, parse_services(partial), NOW + timedelta(seconds=30)))
        self.assertIsNotNone(state.services[0].arrivals[0])
        self.assertEqual(state.services[0].arrivals[0].minutes_at(NOW), 2)
        self.assertEqual(state.services[0].arrivals[1].estimated_at,
                         datetime(2026, 10, 26, 3, 9, tzinfo=timezone.utc))
        self.assertEqual(state.last_updated, NOW)
        self.assertTrue(state.is_stale(NOW + timedelta(seconds=30)))
        state.apply(StopUpdate(0, parse_services(payload()), NOW + timedelta(seconds=60)))
        self.assertEqual(state.last_updated, NOW + timedelta(seconds=60))
        self.assertFalse(state.is_stale(NOW + timedelta(seconds=60)))

    def test_legitimate_empty_estimates_clear_previous_slots(self):
        state = StopState()
        state.apply(StopUpdate(0, parse_services(payload()), NOW))
        state.apply(StopUpdate(0, parse_services({"Services": [{"ServiceNo": "12"}]}),
                               NOW + timedelta(seconds=30)))
        self.assertEqual(state.services[0].arrivals, (None, None, None))
        self.assertFalse(state.is_stale(NOW + timedelta(seconds=30)))

    def test_failed_refresh_keeps_last_success_time_and_marks_stale(self):
        state = StopState()
        state.apply(StopUpdate(0, parse_services(payload()), NOW))
        state.apply(StopUpdate(0, None, NOW + timedelta(seconds=30), "Network error"))
        self.assertEqual(state.last_updated, NOW)
        self.assertEqual(state.services[0].service_no, "12")
        self.assertTrue(state.is_stale(NOW + timedelta(seconds=30)))

    def test_no_result_for_ninety_seconds_is_stale_even_without_error(self):
        state = StopState()
        state.apply(StopUpdate(0, parse_services(payload()), NOW))
        self.assertFalse(state.is_stale(NOW + timedelta(seconds=30)))
        self.assertTrue(state.is_stale(NOW + timedelta(seconds=91)))

    def test_successful_empty_snapshot_clears_old_data_and_error(self):
        state = StopState()
        state.apply(StopUpdate(0, parse_services(payload()), NOW))
        state.apply(StopUpdate(0, (), NOW + timedelta(seconds=30)))
        self.assertEqual(state.services, ())
        self.assertIsNone(state.error)


if __name__ == "__main__":
    unittest.main()
