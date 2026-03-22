"""Redirect sys.stdout / sys.stderr so every print() also feeds the log page."""


class LogCapture:
    def __init__(self, bridge, original):
        self.bridge = bridge
        self.original = original

    def write(self, text):
        if self.original:
            self.original.write(text)
        if text and text.strip():
            self.bridge.log_line.emit(text.rstrip("\n"))

    def flush(self):
        if self.original:
            self.original.flush()
