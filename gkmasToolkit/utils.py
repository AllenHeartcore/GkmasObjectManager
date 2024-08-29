import sys

from rich.console import Console


# macro equivalents
GKMAS_OCTOCACHE_KEY = "1nuv9td1bw1udefk"
GKMAS_OCTOCACHE_IV = "LvAUtf+tnz"


class Logger(Console):

    def __init__(self):
        super().__init__()

    def info(self, message: str):
        self.print(f"[bold white]>>> [Info][/bold white] {message}")

    def success(self, message: str):
        self.print(f"[bold green]>>> [Success][/bold green] {message}")

    def error(self, message: str, fatal: bool = False):
        if fatal:
            self.print(f"[bold red]>>> [Error][/bold red] {message}\n{sys.exc_info()}")
            raise
        else:
            self.print(f"[bold red]>>> [Error][/bold red] {message}")
