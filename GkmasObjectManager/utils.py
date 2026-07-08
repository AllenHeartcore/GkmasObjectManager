"""
utils.py
General-purpose utilities: hashing, decorators, etc.
"""

import json
import re
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes

UNITY_SUFFIX = ".unity3d"
REQUEST_TIMEOUT = 10
PathArgtype = str | Path
# putting these in const.py causes circular imports


def _rget(url: str, **kwargs) -> requests.Response:
    """A wrapper around requests.get() with timeout and sanity check."""
    r = requests.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def _json_load(src: PathArgtype) -> dict | list:
    """Loads a JSON file from the given path."""
    if isinstance(src, str) and urlparse(src).scheme in ("http", "https"):
        return _rget(src).json()  # fetch from 'src' if it's a URL
    with open(src, "r", encoding="utf-8") as fin:
        return json.load(fin)


def _json_dump(obj: dict | list, dst: PathArgtype) -> None:
    """Dumps a JSON file to the given path."""
    with open(dst, "w", encoding="utf-8") as fout:
        json.dump(obj, fout, indent=4, ensure_ascii=False)


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


def remove_unity_suffix(name: str) -> str:
    """Removes the '.unity3d' suffix from a name, if present."""
    # a suboptimal accommodation for choosing to
    # include this suffix in object.assetbundle.name
    return name.removesuffix(UNITY_SUFFIX)


def append_unity_suffix(name: str) -> str:
    """Appends the '.unity3d' suffix to a name, if not already present."""
    return name if name.endswith(UNITY_SUFFIX) else name + UNITY_SUFFIX


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
