"""Lightweight two-stop display; HTTP never runs in a Tk event handler."""

import logging
import os
from datetime import datetime, timezone
from tkinter import Canvas, Frame, Label, Tk

from dotenv import load_dotenv

from bus_data import PollingWorker, StopState
from icons import draw_bus_icon, draw_source_icon

LOGGER = logging.getLogger(__name__)
WINDOW_TITLE = "Bus Arrival Times"
WINDOW_SIZE = "800x480"
BG_COLOR_MAIN = "#333333"
BG_COLOR_HEADER = "#444444"
BG_COLOR_CELL = "#f0f0f0"
FONT_HEADER = ("Arial", 35, "bold")
FONT_SECTION = ("Arial", 26, "bold")
FONT_SERVICE = ("Arial", 24)
FONT_TIME = ("Arial", 26, "bold")


class ArrivalCell:
    def __init__(self, parent):
        self.frame = Frame(parent, bg=BG_COLOR_CELL)
        self.content = Frame(self.frame, bg=BG_COLOR_CELL)
        self.content.pack(anchor="center", pady=2)
        self.label = Label(self.content, text="--", font=FONT_TIME, width=4,
                           bg=BG_COLOR_CELL, fg="#000000", anchor="center")
        self.label.pack(side="left")
        self.bus_icon = Canvas(self.content, width=32, height=32, bg=BG_COLOR_CELL,
                               highlightthickness=0, bd=0, takefocus=0)
        self.bus_icon.pack(side="left", padx=(0, 2))
        self.source_icon = Canvas(self.content, width=24, height=26, bg=BG_COLOR_CELL,
                                  highlightthickness=0, bd=0, takefocus=0)
        self.source_icon.pack(side="left", padx=(0, 3))
        self.source_kind = None
        self.appearance = None

    def render(self, arrival, now):
        minutes = arrival.minutes_at(now) if arrival is not None else None
        text, bg, fg, bus_type, source = "--", BG_COLOR_CELL, "#000000", None, None
        if minutes is not None:
            text = str(minutes) + "m"
            bus_type = arrival.bus_type
            source = {0: "scheduled", 1: "location"}.get(arrival.monitored, "unknown")
            fg = {"SD": "#0000ff", "DD": "#008000"}.get(bus_type, "#000000")
            if minutes <= 2:
                bg, fg = "#FF4C4C", "white"
            elif minutes <= 4:
                bg, fg = "#FFA500", "black"
        appearance = (text, bg, fg, bus_type, source)
        if appearance == self.appearance:
            return
        self.frame.config(bg=bg)
        self.content.config(bg=bg)
        self.label.config(text=text, bg=bg, fg=fg)
        self.bus_icon.config(bg=bg)
        self.source_icon.config(bg=bg)
        draw_bus_icon(self.bus_icon, bus_type, fg)
        draw_source_icon(self.source_icon, source, fg)
        self.appearance = appearance
        self.source_kind = source


def add_icon_legend(parent):
    legend = Frame(parent, bg=BG_COLOR_MAIN)
    legend.pack(side="bottom", fill="x", padx=12, pady=3)
    for kind, label in (("DD", "Double-decker"), ("scheduled", "Scheduled"),
                        ("location", "Location-based"), ("unknown", "Unknown source")):
        group = Frame(legend, bg=BG_COLOR_MAIN)
        group.pack(side="left", padx=(0, 14))
        canvas = Canvas(group, width=32 if kind == "DD" else 24, height=32,
                        bg=BG_COLOR_MAIN, highlightthickness=0, bd=0, takefocus=0)
        canvas.pack(side="left")
        if kind == "DD":
            draw_bus_icon(canvas, kind, "#dddddd")
        else:
            draw_source_icon(canvas, kind, "#dddddd")
        Label(group, text=label, font=("Arial", 10), bg=BG_COLOR_MAIN,
              fg="#dddddd").pack(side="left", padx=(3, 0))


class StopPanel:
    def __init__(self, parent, name):
        self.frame = Frame(parent, bg=BG_COLOR_MAIN)
        self.frame.pack(fill="x", pady=5)
        header = Frame(self.frame, bg=BG_COLOR_MAIN)
        header.pack(fill="x")
        Label(header, text=name, font=FONT_SECTION, bg=BG_COLOR_MAIN,
              fg="#ffcc00").pack(side="left")
        self.status_label = Label(header, text="Loading...", font=("Arial", 11),
                                  bg=BG_COLOR_MAIN, fg="#bbbbbb")
        self.status_label.pack(side="right")
        self.body = Frame(self.frame, bg=BG_COLOR_MAIN)
        self.body.pack(fill="x")
        self.body.grid_columnconfigure(0, weight=1)
        self.rows = {}

    def _create_row(self, service_no):
        frame = Frame(self.body, bg=BG_COLOR_MAIN)
        Label(frame, text=service_no, font=FONT_SERVICE, width=5,
              bg=BG_COLOR_CELL, fg="#000000").grid(row=0, column=0, padx=(0, 8), sticky="ew")
        cells = []
        for column in range(1, 4):
            frame.grid_columnconfigure(column, weight=1)
            cell = ArrivalCell(frame)
            cell.frame.grid(row=0, column=column, sticky="ew")
            cells.append(cell)
        self.rows[service_no] = (frame, cells)

    def render(self, state, now):
        self.status_label.config(text=state.status(now),
                                 fg="#ffcc00" if state.is_stale(now) else "#bbbbbb")
        services = state.services or ()
        wanted = {service.service_no for service in services}
        for service_no in list(self.rows):
            if service_no not in wanted:
                self.rows.pop(service_no)[0].destroy()
        for row, service in enumerate(services):
            if service.service_no not in self.rows:
                self._create_row(service.service_no)
            frame, cells = self.rows[service.service_no]
            frame.grid(row=row, column=0, pady=4, sticky="ew")
            for cell, arrival in zip(cells, service.arrivals):
                cell.render(arrival, now)


class BusArrivalApp:
    def __init__(self, root, api_key, stop_codes, *, worker=None):
        self.root = root
        self.closed = False
        self.worker = worker if worker is not None else PollingWorker(api_key, stop_codes)
        self.states = [StopState(), StopState()]
        root.title(WINDOW_TITLE)
        root.geometry(WINDOW_SIZE)
        root.configure(bg=BG_COLOR_MAIN)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.report_callback_exception
        header = Frame(root, bg=BG_COLOR_HEADER)
        header.pack(fill="x")
        Label(header, text=WINDOW_TITLE, font=FONT_HEADER, bg=BG_COLOR_HEADER,
              fg="white", pady=10).pack(side="left", padx=(10, 0))
        self.time_label = Label(header, font=FONT_SECTION, bg=BG_COLOR_HEADER,
                                fg="white", pady=10)
        self.time_label.pack(side="right", padx=(0, 10))
        add_icon_legend(root)
        content = Frame(root, bg=BG_COLOR_MAIN)
        content.pack(expand=True, fill="both", padx=12, pady=5)
        self.panels = [StopPanel(content, name) for name in ("Downstairs", "Opposite")]
        self.worker.start()
        self.poll_results()
        self.tick()

    def poll_results(self):
        if self.closed:
            return
        try:
            for update in self.worker.drain():
                self.states[update.stop_index].apply(update)
        except Exception:
            LOGGER.exception("Unable to apply arrival update; the next poll will retry")
        finally:
            if not self.closed:
                self.root.after(200, self.poll_results)

    def tick(self):
        if self.closed:
            return
        try:
            now = datetime.now(timezone.utc)
            self.time_label.config(text=now.astimezone().strftime("%I:%M:%S %p"))
            for panel, state in zip(self.panels, self.states):
                try:
                    panel.render(state, now)
                except Exception:
                    LOGGER.exception("Unable to draw stop; the next tick will retry")
        except Exception:
            LOGGER.exception("Unable to update display clock")
        finally:
            if not self.closed:
                self.root.after(1000, self.tick)

    def report_callback_exception(self, exc_type, value, traceback):
        LOGGER.error("Unhandled display callback", exc_info=(exc_type, value, traceback))

    def close(self):
        if not self.closed:
            self.closed = True
            self.worker.stop()
            self.root.destroy()


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    names = ("API_KEY", "BUS_STOP_CODE_A", "BUS_STOP_CODE_B")
    values = [os.getenv(name, "").strip() for name in names]
    missing = [name for name, value in zip(names, values) if not value]
    if missing:
        LOGGER.error("Missing configuration: %s", ", ".join(missing))
        return 2
    root = Tk()
    app = BusArrivalApp(root, values[0], values[1:])
    try:
        root.mainloop()
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
