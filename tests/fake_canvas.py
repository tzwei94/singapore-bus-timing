class RecordingCanvas:
    """Record the public Canvas drawing operations without a graphical session."""

    def __init__(self):
        self.items = {}
        self.created_total = 0

    def delete(self, tag):
        if tag != "all":
            raise AssertionError("Unsupported Canvas deletion")
        self.items.clear()

    def _create(self, shape, coords, options):
        self.created_total += 1
        self.items[self.created_total] = (shape, coords, options)
        return self.created_total

    def create_rectangle(self, *coords, **options):
        return self._create("rectangle", coords, options)

    def create_oval(self, *coords, **options):
        return self._create("oval", coords, options)

    def create_line(self, *coords, **options):
        return self._create("line", coords, options)

    def create_text(self, *coords, **options):
        return self._create("text", coords, options)
