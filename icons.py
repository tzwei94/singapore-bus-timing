"""Small native Canvas pictograms; no image files or emoji fonts required."""


def draw_bus_icon(canvas, bus_type, color):
    canvas.delete("all")
    if bus_type != "DD":
        return
    canvas.create_rectangle(4, 2, 27, 26, outline=color, width=2)
    for y in (5, 15):
        for x in (7, 14, 21):
            canvas.create_rectangle(x, y, x + 4, y + 5, fill=color, width=0)
    canvas.create_line(4, 12, 27, 12, fill=color, width=2)
    canvas.create_oval(6, 24, 12, 30, fill=color, outline=color)
    canvas.create_oval(20, 24, 26, 30, fill=color, outline=color)


def draw_source_icon(canvas, source, color):
    canvas.delete("all")
    if source == "scheduled":
        canvas.create_oval(2, 2, 21, 21, outline=color, width=2)
        canvas.create_line(11, 6, 11, 12, 16, 15, fill=color, width=2)
    elif source == "location":
        canvas.create_oval(4, 1, 20, 17, outline=color, width=2)
        canvas.create_line(5, 13, 12, 24, 19, 13, fill=color, width=2)
        canvas.create_oval(9, 6, 15, 12, fill=color, outline=color)
    elif source is not None:
        canvas.create_text(12, 12, text="?", fill=color, font=("Arial", 17, "bold"))
