"""
utils.py
General-purpose utilities: hashing, decorators, etc.
"""

import re
from typing import Callable

from cryptography.hazmat.primitives import hashes


def sha256sum(data: bytes) -> bytes:
    """Calculates SHA-256 hash of the given data."""
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize()


def md5sum(data: bytes) -> bytes:
    """Calculates MD5 hash of the given data."""
    digest = hashes.Hash(hashes.MD5())
    digest.update(data)
    return digest.finalize()


def nocache(func) -> Callable:
    """Decorator to temporarily disable caching for GkmasDummyMedia and children."""

    from .media import GkmasDummyMedia

    def wrapper(*args, **kwargs):
        original = GkmasDummyMedia.ENABLE_CACHE
        GkmasDummyMedia.ENABLE_CACHE = False
        try:
            return func(*args, **kwargs)
        finally:
            GkmasDummyMedia.ENABLE_CACHE = original

    return wrapper


def make_caption_map(commands: list[dict]) -> dict[str, str]:
    """
    Converts a list of adventure commands into a mapping
    of voicelines' *in-archive aliases* to their captions.
    """

    from .const import DEFAULT_USERNAME

    caption_map = {}

    commands = sorted(
        filter(lambda cmd: cmd["cmd"] in ["message", "voice"], commands),
        key=lambda cmd: cmd["clip"]["_startTime"],
    )  # m- and v- commands don't necessarily go together in raw data

    for cmd1, cmd2 in zip(commands, commands[1:]):
        if cmd1["cmd"] == "message" and cmd2["cmd"] == "voice":

            caption = cmd1.get("text", "").strip().replace(r"\n", "")
            caption = caption.replace("{user}", DEFAULT_USERNAME)

            # Superscripts look like "<r\\=AAA>BBB</r>", where BBB
            # is pronounced as AAA. We keep the pronunciation here.
            caption = re.sub(r"<r\\=([^>]+)>.*</r>", r"\1", caption)
            caption = re.sub(r"<[^<>]*>", "", caption)  # remove XML tags

            caption_map[cmd2["voice"]] = caption

    return caption_map
