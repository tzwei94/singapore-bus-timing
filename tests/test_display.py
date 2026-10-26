import importlib.util
import os
import threading
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from bus_data import Arrival, PollingWorker, StopState, StopUpdate, parse_services
from fake_canvas import RecordingCanvas


class Widget:
    """Small widget/scheduler double; no native display or API is used."""

    def __init__(self, parent=None, **options):
        self.options = options
        self.children = []
        self.callbacks = []
        self.destroyed = False
        if parent is not None:
            parent.children.append(self)

    def pack(self, **kwargs): pass
    def grid(self, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def configure(self, **kwargs): self.options.update(kwargs)
    config = configure
    def title(self, value): pass
    def geometry(self, value): pass
    def protocol(self, *args): pass
    def mainloop(self): pass
    def winfo_children(self): return list(self.children)
    def cget(self, name): return self.options.get(name)
    def after(self, delay, callback): self.callbacks.append((delay, callback))
    def destroy(self): self.destroyed = True


class WorkerDouble:
    def __init__(self):
        self.updates = []
        self.fail = False

    def start(self): pass
    def stop(self): pass
    def drain(self):
        if self.fail:
            raise RuntimeError("injected queue consumer failure")
        updates, self.updates = self.updates, []
        return updates


class Canvas(Widget, RecordingCanvas):
    def __init__(self, parent=None, **options):
        Widget.__init__(self, parent, **options)
        RecordingCanvas.__init__(self)


class EmptyResponse:
    status_code = 200
    def json(self): return {"Services": []}


def all_widgets(widget):
    yield widget
    for child in widget.children:
        yield from all_widgets(child)


class DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_tk = types.ModuleType("tkinter")
        fake_tk.Tk = fake_tk.Label = fake_tk.Frame = Widget
        fake_tk.Canvas = Canvas
        spec = importlib.util.spec_from_file_location(
            "bus_display_under_test", Path(__file__).parents[1] / "main.py"
        )
        cls.module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"tkinter": fake_tk}), patch.dict(
            os.environ, {"API_KEY": "test", "BUS_STOP_CODE_A": "A", "BUS_STOP_CODE_B": "B"}
        ), patch("requests.get", return_value=EmptyResponse()), patch("dotenv.load_dotenv"):
            spec.loader.exec_module(cls.module)

    def app(self):
        root, worker = Widget(), WorkerDouble()
        return self.module.BusArrivalApp(root, "test", ("A", "B"), worker=worker), root, worker

    def test_consumer_error_does_not_unschedule_future_updates(self):
        app, root, worker = self.app()
        root.callbacks.clear()
        worker.fail = True
        with self.assertLogs(self.module.LOGGER, level="ERROR"):
            app.poll_results()
        self.assertTrue(any(callback == app.poll_results for _, callback in root.callbacks))
        worker.fail = False
        worker.updates = [StopUpdate(0, (), datetime.now(timezone.utc))]
        app.poll_results()
        self.assertEqual(app.states[0].services, ())

    def test_render_error_does_not_stop_clock_tick_or_other_stop(self):
        app, root, _ = self.app()
        root.callbacks.clear()
        with patch.object(app.panels[0], "render", side_effect=RuntimeError("bad widget")), patch.object(
            app.panels[1], "render", wraps=app.panels[1].render
        ) as healthy_panel, self.assertLogs(self.module.LOGGER, level="ERROR"):
            app.tick()
        self.assertTrue(any(callback == app.tick for _, callback in root.callbacks))
        self.assertEqual(healthy_panel.call_count, 1)

    def test_real_worker_can_wait_for_network_while_ui_keeps_scheduling(self):
        entered, release = threading.Event(), threading.Event()

        def slow_fetch(*args, **kwargs):
            entered.set()
            release.wait(2)
            return ()

        worker = PollingWorker("test", ("A", "B"), fetcher=slow_fetch)
        self.addCleanup(release.set)
        self.addCleanup(worker.stop)
        root = Widget()
        app = self.module.BusArrivalApp(root, "test", ("A", "B"), worker=worker)
        self.assertTrue(entered.wait(1))
        root.callbacks.clear()
        app.tick()
        app.poll_results()
        self.assertEqual(len(root.callbacks), 2)
        self.assertNotEqual(worker.thread.ident, threading.get_ident())
        app.close()
        release.set()
        worker.thread.join(1)
        self.assertFalse(worker.thread.is_alive())

    def test_close_prevents_rescheduling_callbacks(self):
        app, root, _ = self.app()
        app.close()
        root.callbacks.clear()
        app.tick()
        app.poll_results()
        self.assertEqual(root.callbacks, [])
        self.assertTrue(root.destroyed)

    def test_real_panel_shows_missing_slots_colors_and_dd_icons(self):
        now = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)
        services = parse_services({"Services": [{"ServiceNo": "12",
            "NextBus": {},
            "NextBus2": {"EstimatedArrival": "2026-10-26T11:08:00+08:00", "Type": "DD"},
            "NextBus3": {"EstimatedArrival": "2026-10-26T11:02:00+08:00", "Type": "SD"},
        }]})
        root = Widget()
        panel = self.module.StopPanel(root, "Downstairs")
        state = StopState()
        state.apply(StopUpdate(0, services, now))
        panel.render(state, now)
        widgets = list(all_widgets(root))
        self.assertIn("--", [w.cget("text") for w in widgets])
        dd = next(w for w in widgets if w.cget("text") == "8m")
        self.assertEqual(dd.cget("fg"), "#008000")
        self.assertFalse(any("(DD)" in str(w.cget("text")) for w in widgets))
        urgent = next(w for w in widgets if w.cget("text") == "2m")
        self.assertEqual(urgent.cget("bg"), "#FF4C4C")
        before = len(widgets)
        for _ in range(100):
            panel.render(state, now)
        self.assertEqual(len(list(all_widgets(root))), before)

    def test_arrival_icons_follow_source_and_hide_for_empty_slots(self):
        now = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)
        state = StopState()
        state.apply(StopUpdate(0, parse_services({"Services": [{"ServiceNo": "12",
            "NextBus": {"EstimatedArrival": "2026-10-26T11:02:00+08:00", "Type": "DD", "Monitored": 0},
            "NextBus2": {"EstimatedArrival": "2026-10-26T11:08:00+08:00", "Type": "DD", "Monitored": 1},
        }]}), now))
        panel = self.module.StopPanel(Widget(), "Downstairs")
        panel.render(state, now)
        scheduled, location, empty = panel.rows["12"][1]
        self.assertEqual(scheduled.source_kind, "scheduled")
        self.assertEqual(location.source_kind, "location")
        self.assertTrue(scheduled.bus_icon.items)
        self.assertEqual(scheduled.label.cget("fg"), "white")
        self.assertEqual(empty.source_icon.items, {})
        self.assertEqual(empty.bus_icon.items, {})
        before = scheduled.source_icon.created_total + scheduled.bus_icon.created_total
        for _ in range(100):
            panel.render(state, now)
        self.assertEqual(scheduled.source_icon.created_total + scheduled.bus_icon.created_total, before)

    def test_transient_icon_draw_failure_is_retried_on_next_tick(self):
        now = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)
        arrival = Arrival(datetime(2026, 10, 26, 3, 8, tzinfo=timezone.utc), "DD", 0)
        cell = self.module.ArrivalCell(Widget())
        with patch.object(self.module, "draw_source_icon", side_effect=RuntimeError("temporary draw error")):
            with self.assertRaises(RuntimeError):
                cell.render(arrival, now)
        cell.render(arrival, now)
        self.assertTrue(cell.source_icon.items)

    def test_expired_arrival_removes_vehicle_and_source_icons(self):
        now = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)
        arrival = Arrival(datetime(2026, 10, 26, 3, 8, tzinfo=timezone.utc), "DD", 1)
        cell = self.module.ArrivalCell(Widget())
        cell.render(arrival, now)
        self.assertTrue(cell.bus_icon.items)
        cell.render(arrival, datetime(2026, 10, 26, 3, 10, tzinfo=timezone.utc))
        self.assertEqual(cell.label.cget("text"), "--")
        self.assertEqual(cell.bus_icon.items, {})
        self.assertEqual(cell.source_icon.items, {})


if __name__ == "__main__":
    unittest.main()
