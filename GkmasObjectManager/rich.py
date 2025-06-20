"""
rich.py
Rich console logger and progress reporter.
"""

from queue import Queue
from typing import Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn


class Logger(Console):
    """
    A rich console logger with custom log levels.

    Methods:
        info(message: str): Logs an informational message in white text.
        success(message: str): Logs a success message in green text.
        warning(message: str): Logs a warning message in yellow text.
        error(message: str): Logs an error message in red text
            followed by traceback, and raises an error.
    """

    def __init__(self):
        super().__init__()

    def info(self, message: str):
        self.print(f"[bold white][Info][/bold white] {message}")

    def success(self, message: str):
        self.print(f"[bold green][Success][/bold green] {message}")

    def warning(self, message: str):
        self.print(f"[bold yellow][Warning][/bold yellow] {message}")

    def error(self, message: str):
        self.print(f"[bold red][Error][/bold red] {message}")
        raise RuntimeError(message)


class ProgressReporter:
    """
    An interface for either printing a progress bar to the console,
    or passing progress updates to a GUI.

    Attributes:
        title (str): "Master" description for the task, usually a filename.
        total (int): Number of units to process, usually the file size in bytes.
        progress (Optional[Progress]): Rich Progress instance for console output.
        task_id (Optional[int]): Task ID for GUI progress updates.
        upstream (Optional[Queue]): Provides callback to propagate updates to GUI.
    """

    title: str
    total: int
    progress: Optional[Progress] = None
    task_id: Optional[int] = None
    upstream: Optional[Queue[dict]] = None
    is_standalone: bool = False

    status2color = {
        "update": "bold cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
    }

    def __init__(self, total: int, title: str = "Progress"):
        # 'title' can be omitted in GUI mode, but 'total' is mandatory
        assert title, "Title cannot be an empty string"
        assert total > 0, "Total must be positive"
        self.title = title
        self.total = total

    def register(
        self,
        progress: Optional[Progress] = None,
        task_id: Optional[int] = None,
        upstream: Optional[Queue[dict]] = None,
        **kwargs,  # wildcard, catches any unused parameters for compatibility
    ):
        """
        Registers the progress reporter with a Progress instance or task ID.

        Args:
            progress (Progress, optional): Rich Progress instance for console output.
                Should only be instantiated in GkmasManifest.download()
                for a batch of tasks, to support multiple bar updates.
                If None, a disposable Progress instance is created.
            task_id (int, optional): Task ID for GUI progress updates.
                Again, should only be provided by GkmasManifest.download().
            upstream (Queue[dict], optional): Provides callback to propagate updates
                to GUI. Suppresses console output if set.
        """
        self.upstream = upstream
        if not progress:
            assert (
                task_id is None
            ), "task_id should only be provided with a Progress instance"
            self.progress = Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
            )
            self.task_id = self.progress.add_task(self.title)
            self.is_standalone = True
        else:
            assert (
                task_id is not None
            ), "task_id should be provided with a Progress instance"
            self.progress = progress
            self.task_id = task_id
            self.is_standalone = False

    def _rich_descr(self, stage: str, color: str) -> str:
        return f"[white]{self.title}[/] - [{color}]{stage}[/]"

    def _emit_progress(
        self,
        stage: str,
        advance: Optional[int] = None,
        total: Optional[int] = None,
    ):

        # unconditional task update; serves as a hidden counter
        # if self.upstream is set and visible=False
        self.progress.update(
            self.task_id,
            description=self._rich_descr(stage, color=self.status2color["update"]),
            advance=advance,
            total=total,
        )

        if self.upstream:
            self.upstream.put(
                {
                    "stage": stage,
                    "completed": self.progress.tasks[self.task_id].completed,
                    "total": total if total is not None else self.total,
                }
            )

    def _emit_message(self, status: str, message: str):

        if self.upstream:
            self.upstream.put({"event": status, "message": message})
            return

        self.progress.print(
            self._rich_descr(message, color=self.status2color.get(status, "white"))
        )

    def start(self):
        """Starts the progress bar with the initial title."""

        if not self.progress:
            return

        if self.is_standalone:
            self.progress.start()
        elif not self.upstream:  # no console display in GUI mode
            # might be redundant since GUI never runs non-standalone Reporters
            self.progress.update(self.task_id, visible=True)

        self._emit_progress("Starting", total=self.total)

    def update(self, stage: str, advance: Optional[int] = None):
        """
        Updates the progress bar by the specified number of units.

        Args:
            stage (str): Description of the current stage
                (download, deobfuscate, convert, etc.)
            advance (int, optional): Usually the number of bytes in a chunk.
        """

        if not self.progress:
            return

        self._emit_progress(stage, advance=advance)

    def success(self, message: str = "Completed"):
        """
        Stops the progress bar and prints a success message to the console.

        Args:
            message (str): A success message to print.
                Defaults to "Completed".
        """

        if not self.progress:
            return

        if self.is_standalone:
            self.progress.stop()
        else:
            self.progress.remove_task(self.task_id)

        self._emit_message("success", message)

    def warning(self, message: str):
        """
        Logs a warning message to the console.
        Used in media/ where logger.warning() would get overwritten by progress bars.

        Args:
            message (str): A warning message to print.
        """

        if not self.progress:
            return

        self._emit_message("warning", message)

    def error(self, message: str):
        """
        Logs an error message to the console and raises an error.
        Used in media/ where logger.error() would get overwritten by progress bars.

        Args:
            message (str): An error message to print.
        """

        if not self.progress:
            return

        self._emit_message("error", message)
        raise RuntimeError(message)
