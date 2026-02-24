"""FootballSpinner widget - ASCII football animation."""

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static
from textual.app import ComposeResult


# ASCII football frames for animation
BALL_FRAMES = [
    "  ,@,  \n /`'\\  \n  |    \n / \\  ",
    "  ,@,  \n /`'\\  \n  |    \n/ _ \\ ",
    "  .@.  \n (`')  \n  |    \n / \\  ",
    "  ,@,  \n /`'\\  \n  |    \n \\ /  ",
]

IDLE_FRAME = "  ,@,  \n /`'\\  \n  |    \n / \\  "


class FootballSpinner(Widget):
    """Animated ASCII football spinner."""

    DEFAULT_CSS = """
    FootballSpinner {
        width: 10;
        height: 5;
        content-align: center middle;
        padding: 0 1;
    }
    """

    active: reactive[bool] = reactive(False)
    _frame_index: int = 0
    _timer = None

    def compose(self) -> ComposeResult:
        yield Static(IDLE_FRAME, id="spinner-frame")

    def watch_active(self, value: bool) -> None:
        if value:
            self._frame_index = 0
            self._timer = self.set_interval(0.3, self._advance_frame)
        else:
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
            self._frame_index = 0
            try:
                self.query_one("#spinner-frame", Static).update(IDLE_FRAME)
            except Exception:
                pass

    def _advance_frame(self) -> None:
        self._frame_index = (self._frame_index + 1) % len(BALL_FRAMES)
        try:
            self.query_one("#spinner-frame", Static).update(BALL_FRAMES[self._frame_index])
        except Exception:
            pass
