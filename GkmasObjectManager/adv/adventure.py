"""
adv/adventure.py
Adventure (story script) plugin for GkmasResource.
"""

from ..log import Logger
from ..media import GkmasDummyMedia
from .parser import GkadvCommandParser

import json


logger = Logger()
parser = GkadvCommandParser()


class GkmasAdventure(GkmasDummyMedia):
    """Handler for adventure story scripts."""

    def __init__(self, name: str, raw: bytes, mtime: str = ""):
        super().__init__(name, raw, mtime)
        self.mimetype = "text"
        self.converted_format = "json"

        self.commands = [
            parser.process(line) for line in raw.decode("utf-8").splitlines()
        ]

    def _convert(self, raw: bytes, **kwargs) -> bytes:
        # only for compatibility with GkmasResource
        return bytes(
            json.dumps(
                self.commands,
                indent=4,
                ensure_ascii=False,
            ),
            "utf-8",
        )
