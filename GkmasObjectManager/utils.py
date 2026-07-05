"""
utils.py
General-purpose utilities: hashing, decorators, etc.
"""

import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes

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
