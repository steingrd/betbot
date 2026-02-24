"""EventLog widget - timestamped, color-coded log messages."""

from datetime import datetime

from textual.widgets import RichLog


class EventLog(RichLog):
    """Scrollable event log with timestamps and color-coded messages."""

    DEFAULT_CSS = """
    EventLog {
        dock: right;
        width: 28;
        border-left: solid $accent;
        padding: 0 1;
    }
    """

    MAX_LINES = 500
    _line_count: int = 0

    def log_info(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(f"[dim]{ts}[/]  {message}")
        self._line_count += 1
        self._trim()

    def log_success(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(f"[dim]{ts}[/]  [green]{message}[/]")
        self._line_count += 1
        self._trim()

    def log_warning(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(f"[dim]{ts}[/]  [yellow]{message}[/]")
        self._line_count += 1
        self._trim()

    def log_error(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(f"[dim]{ts}[/]  [bold red]{message}[/]")
        self._line_count += 1
        self._trim()

    def _trim(self) -> None:
        if self._line_count > self.MAX_LINES:
            self.clear()
            self._line_count = 0
