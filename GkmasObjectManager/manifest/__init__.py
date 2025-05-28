"""
manifest/
Manifest (object database) management.
Entry point of the GkmasObjectManager package.
"""

import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from google.protobuf.message import DecodeError

from ..const import (
    GKMAS_API_HEADER,
    GKMAS_API_URL,
    GKMAS_API_URL_PC,
    GKMAS_OCTOCACHE_IV,
    GKMAS_OCTOCACHE_KEY,
    GKMAS_ONLINEPDB_KEY,
    GKMAS_ONLINEPDB_KEY_PC,
    PathArgtype,
)
from .decrypt import AESCBCDecryptor
from .manifest import GkmasManifest
from .octodb_pb2 import pdbytes2dict


def fetch(base_revision: int = 0, pc: bool = False) -> GkmasManifest:
    """
    Requests an online manifest by the specified revision.
    Algorithm courtesy of github.com/DreamGallery/HatsuboshiToolkit

    Args:
        base_revision (int): The "base" revision number of the manifest.
            This API return the *difference* between the specified base
            revision and the latest. Defaults to 0 (standalone latest).
        pc (bool): Whether to use the PC manifest API.
            Defaults to False (mobile).
    """
    url = urljoin(GKMAS_API_URL_PC if pc else GKMAS_API_URL, str(base_revision))
    req = requests.get(url, headers=GKMAS_API_HEADER, timeout=10)
    req.raise_for_status()  # Raise an error for bad responses
    enc = req.content
    dec = AESCBCDecryptor(
        GKMAS_ONLINEPDB_KEY_PC if pc else GKMAS_ONLINEPDB_KEY, enc[:16]
    ).process(enc[16:])
    return GkmasManifest(pdbytes2dict(dec), base_revision=base_revision)


def load(src: PathArgtype, base_revision: int = 0) -> GkmasManifest:
    """
    Initializes a manifest from the given offline source.
    The protobuf referred to can be either encrypted or not.
    Also supports importing from JSON.

    Args:
        src (Union[str, Path]): Path to the manifest file.
            Can be the path to
            - an encrypted octocache (usually named 'octocacheevai'),
            - a decrypted protobuf, or
            - a JSON file exported from another manifest.
        base_revision (int) = 0: The revision number of the base manifest.
            **Must be manually specified if loading a diff genereated
            by GkmasObjectManager older than or equal to v0.4-beta.**
    """
    try:
        return GkmasManifest(
            json.loads(Path(src).read_text(encoding="utf-8")),
            base_revision,
        )
    except json.JSONDecodeError:
        enc = Path(src).read_bytes()
        try:
            return GkmasManifest(pdbytes2dict(enc), base_revision)
        except DecodeError:
            dec = AESCBCDecryptor(GKMAS_OCTOCACHE_KEY, GKMAS_OCTOCACHE_IV).process(enc)
            return GkmasManifest(pdbytes2dict(dec[16:]), base_revision)  # trim md5 hash
