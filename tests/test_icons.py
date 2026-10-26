import unittest

from fake_canvas import RecordingCanvas
from icons import draw_bus_icon, draw_source_icon


class IconTests(unittest.TestCase):
    def test_double_decker_has_two_visibly_separate_window_rows(self):
        canvas = RecordingCanvas()
        draw_bus_icon(canvas, "DD", "white")
        windows = [coords for shape, coords, options in canvas.items.values()
                   if shape == "rectangle" and options.get("fill") == "white"]
        self.assertGreaterEqual(len(windows), 4)
        self.assertEqual(len({coords[1] for coords in windows}), 2)

    def test_scheduled_and_location_icons_are_distinguishable_by_shape(self):
        canvas = RecordingCanvas()
        draw_source_icon(canvas, "scheduled", "black")
        clock = [(shape, coords) for shape, coords, _ in canvas.items.values()]
        draw_source_icon(canvas, "location", "black")
        pin = [(shape, coords) for shape, coords, _ in canvas.items.values()]
        self.assertNotEqual(clock, pin)
        self.assertTrue(any(shape == "oval" for shape, _ in clock))

    def test_unknown_source_has_question_symbol_and_empty_source_has_no_icon(self):
        canvas = RecordingCanvas()
        draw_source_icon(canvas, "unknown", "black")
        self.assertTrue(any(options.get("text") == "?" for _, _, options in canvas.items.values()))
        draw_source_icon(canvas, None, "black")
        self.assertEqual(canvas.items, {})

    def test_repeated_icon_updates_replace_items_instead_of_accumulating(self):
        canvas = RecordingCanvas()
        for index in range(100):
            draw_bus_icon(canvas, "DD" if index % 2 else "SD", "black")
            self.assertLessEqual(len(canvas.items), 12)
        draw_bus_icon(canvas, None, "black")
        self.assertEqual(canvas.items, {})


if __name__ == "__main__":
    unittest.main()
