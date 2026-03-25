"""Redirect sys.stdout / sys.stderr so every print() also feeds the log page."""


class LogCapture:
    def __init__(self, bridge, original):
        self.bridge = bridge
        self.original = original
        self.encoding = getattr(original, "encoding", "utf-8")
        self.errors = getattr(original, "errors", "strict")

    def write(self, text):
        if self.original:
            self.original.write(text)
        if text and text.strip():
            self.bridge.log_line.emit(text.rstrip("\n"))

    def flush(self):
        if self.original:
            self.original.flush()

    def fileno(self):
        if self.original:
            return self.original.fileno()
        raise OSError("no underlying fileno")

    def isatty(self):
        if self.original:
            return self.original.isatty()
        return False

    def __getattr__(self, name):
        return getattr(self.original, name)
