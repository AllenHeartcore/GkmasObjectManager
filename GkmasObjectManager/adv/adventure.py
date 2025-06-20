"""
adv/adventure.py
Adventure (story script) plugin for GkmasResource.
"""

import json
import re

from ..media import GkmasDummyMedia
from ..utils import make_caption_map
from .parser import GkadvCommandParser

parser = GkadvCommandParser()


class GkmasAdventure(GkmasDummyMedia):
    """Handler for adventure story scripts."""

    _commands: list[dict] = []

    def _init_mimetype(self):
        self.mimetype = "text"
        self.default_converted_format = "json"

    @property
    def commands(self) -> list[dict]:
        if not self._commands:
            self._commands = [
                parser.process(line) for line in self.raw.decode("utf-8").splitlines()
            ]
        return self._commands

    @property
    def caption_map(self) -> dict[str, str]:
        """For voice archive captioning in frontend only."""
        return make_caption_map(self.commands)

    def _convert(self, raw: bytes) -> bytes:
        # only for compatibility with GkmasResource
        return bytes(
            json.dumps(self.commands, indent=4, ensure_ascii=False),
            "utf-8",
        )
