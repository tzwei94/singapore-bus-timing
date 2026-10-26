"""Arrival parsing and background polling, independent of Tkinter."""

import logging
import queue
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

import requests

LOGGER = logging.getLogger(__name__)
API_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
REQUEST_TIMEOUT = (3.05, 10)
POLL_INTERVAL = 30
STALE_SECONDS = 90


@dataclass(frozen=True)
class Arrival:
    estimated_at: datetime
    bus_type: str
    monitored: Optional[int] = None

    def minutes_at(self, now):
        seconds = (self.estimated_at - now).total_seconds()
        # Cached buses must not remain on screen as negative/zero-minute arrivals.
        return None if seconds < -60 else max(0, round(seconds / 60))


@dataclass(frozen=True)
class Service:
    service_no: str
    arrivals: Tuple[Optional[Arrival], Optional[Arrival], Optional[Arrival]]
    invalid_slots: Tuple[bool, bool, bool] = (False, False, False)


def parse_services(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("Services"), list):
        raise ValueError("Response has no Services array")
    services = []
    seen = set()
    for record in payload["Services"]:
        if not isinstance(record, dict):
            continue
        service_no = record.get("ServiceNo")
        if not isinstance(service_no, str) or not service_no.strip():
            continue
        service_no = service_no.strip()
        if service_no in seen:
            continue
        seen.add(service_no)
        arrivals, invalid_slots = [], []
        for name in ("NextBus", "NextBus2", "NextBus3"):
            bus = record.get(name)
            arrival = None
            invalid = bus is not None and not isinstance(bus, dict)
            if isinstance(bus, dict) and bus.get("EstimatedArrival") not in (None, ""):
                try:
                    eta = datetime.fromisoformat(bus["EstimatedArrival"].replace("Z", "+00:00"))
                    if eta.tzinfo is None:
                        raise ValueError("Arrival timestamp has no timezone")
                    bus_type = bus.get("Type")
                    monitored = bus.get("Monitored")
                    if isinstance(monitored, str) and monitored.strip() in ("0", "1"):
                        monitored = int(monitored.strip())
                    elif type(monitored) is not int or monitored not in (0, 1):
                        monitored = None
                    arrival = Arrival(eta, bus_type if isinstance(bus_type, str) else "Other", monitored)
                except (AttributeError, TypeError, ValueError):
                    invalid = True
                    LOGGER.debug("Ignoring invalid arrival timestamp")
            arrivals.append(arrival)
            invalid_slots.append(invalid)
        services.append(Service(service_no, tuple(arrivals), tuple(invalid_slots)))
    if payload["Services"] and not services:
        raise ValueError("Response contains no valid service records")
    return tuple(services)


def fetch_bus_arrival(api_key, bus_stop_code, *, session=None, timeout=REQUEST_TIMEOUT):
    client = session if session is not None else requests
    response = client.get(
        API_URL,
        params={"BusStopCode": bus_stop_code},
        headers={"AccountKey": api_key, "accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_services(response.json())


@dataclass(frozen=True)
class StopUpdate:
    stop_index: int
    services: Optional[Tuple[Service, ...]]
    updated_at: datetime
    error: Optional[str] = None


@dataclass
class StopState:
    services: Optional[Tuple[Service, ...]] = None
    last_updated: Optional[datetime] = None
    error: Optional[str] = None

    def apply(self, update):
        if update.services is not None:
            partial = any(any(service.invalid_slots) for service in update.services)
            previous = {service.service_no: service for service in self.services or ()}
            merged = []
            for service in update.services:
                old = previous.get(service.service_no)
                arrivals = tuple(
                    old.arrivals[index] if invalid and old is not None else arrival
                    for index, (arrival, invalid) in enumerate(zip(service.arrivals, service.invalid_slots))
                )
                merged.append(Service(service.service_no, arrivals, service.invalid_slots))
            self.services = tuple(merged)
            if partial:
                self.error = update.error or "Invalid arrival data"
                return
            self.last_updated = update.updated_at
        self.error = update.error

    def is_stale(self, now):
        return bool(self.error or self.last_updated is None
                    or (now - self.last_updated).total_seconds() > STALE_SECONDS)

    def status(self, now):
        if self.last_updated is None:
            if self.error and self.services is not None:
                return "Partial data - retrying"
            return "Unavailable - retrying" if self.error else "Loading..."
        updated = self.last_updated.astimezone().strftime("%H:%M:%S")
        if self.error:
            return "STALE - retrying | last update " + updated
        if self.is_stale(now):
            return "STALE | last update " + updated
        prefix = "No services reported | " if not self.services else ""
        return prefix + "Updated " + updated


def error_summary(error):
    if isinstance(error, requests.Timeout):
        return "Request timed out"
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return "HTTP " + str(error.response.status_code)
    if isinstance(error, requests.ConnectionError):
        return "Network error"
    return type(error).__name__


class PollingWorker:
    """One HTTP worker; only the main thread consumes results and edits widgets."""

    def __init__(self, api_key, stops, *, fetcher=fetch_bus_arrival, interval=POLL_INTERVAL):
        self.api_key = api_key
        self.stops = tuple(stops)
        self.fetcher = fetcher
        self.interval = interval
        self.session = requests.Session()
        self.results = queue.Queue(maxsize=max(1, len(self.stops)))
        self.stopped = threading.Event()
        self.thread = None

    def poll_once(self):
        for index, stop in enumerate(self.stops):
            if self.stopped.is_set():
                break
            try:
                services = self.fetcher(self.api_key, stop, session=self.session)
                if any(any(service.invalid_slots) for service in services):
                    LOGGER.warning("Partial arrival data for stop %s; retrying", stop)
                update = StopUpdate(index, services, datetime.now(timezone.utc))
            except Exception as error:
                # Do not log credentials or response bodies. A bad stop must not
                # terminate the worker or prevent the other stop's refresh.
                summary = error_summary(error)
                LOGGER.warning("Refresh failed for stop %s: %s; retrying", stop, summary)
                update = StopUpdate(index, None, datetime.now(timezone.utc), summary)
            try:
                self.results.put_nowait(update)
            except queue.Full:
                try:
                    self.results.get_nowait()
                except queue.Empty:
                    pass
                self.results.put_nowait(update)

    def drain(self):
        updates = []
        while True:
            try:
                updates.append(self.results.get_nowait())
            except queue.Empty:
                return updates

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, name="bus-arrivals", daemon=True)
            self.thread.start()

    def _run(self):
        try:
            while not self.stopped.is_set():
                self.poll_once()
                self.stopped.wait(self.interval)
        finally:
            self.session.close()

    def stop(self):
        self.stopped.set()
        if self.thread is None:
            self.session.close()
