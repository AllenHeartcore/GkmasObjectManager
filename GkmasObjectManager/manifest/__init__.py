"""
manifest/
Manifest (object database) management.
Entry point of the GkmasObjectManager package.
"""

from json import JSONDecodeError
from pathlib import Path
from urllib.parse import urljoin

from google.protobuf.message import DecodeError

from ..const import (
    GKMAS_API_HEADER,
    GKMAS_API_URL,
    GKMAS_API_URL_PC,
    GKMAS_OCTOCACHE_IV,
    GKMAS_OCTOCACHE_KEY,
    GKMAS_ONLINEPDB_KEY,
    GKMAS_ONLINEPDB_KEY_PC,
    WAYBACK_COMMITS_LOG_LOCAL,
    WAYBACK_COMMITS_LOG_LOCAL_PC,
    WAYBACK_COMMITS_LOG_REMOTE,
    WAYBACK_COMMITS_LOG_REMOTE_PC,
    WAYBACK_MANIFEST_URL_TEMPLATE,
    WAYBACK_MANIFEST_URL_TEMPLATE_PC,
    PathArgtype,
)
from ..utils import _json_load, _rget
from .decrypt import AESCBCDecryptor
from .manifest import GkmasManifest
from .octodb_pb2 import pdbytes2dict
from .versioning import GkmasManifestVersion


def fetch(
    target_version: int | str = 0,
    base_revision: int = 0,
    pc: bool = False,
    _use_local_commits_log: bool = False,
) -> GkmasManifest:
    """
    Requests an online manifest by the specified version.
    Algorithm courtesy of github.com/DreamGallery/HatsuboshiToolkit

    Args:
        target_version (int | str): The version of the manifest to fetch.
            Defaults to 0 (latest).
            String versions take the form of "<era>:<revision>",
            and previous eras must be explicitly specified.
            Older versions will be fetched from the commit history
            of **this repository**, instead of the game server.
        base_revision (int): The "base" revision number of the manifest.
            Defaults to 0 (standalone latest).
            This API return the *difference* between the specified base
            revision and the latest.
        pc (bool): Whether to use the PC manifest API.
            Defaults to False (mobile).
    """
    #   _use_local_commits_log (bool): Whether to use the local "commits log".
    #       Defaults to False.
    #       Falls back to the remote "commits log" if the local one is not found.
    #       Exclusively used in rebuilding "objects log" before remote "commits log" is updated.
    #       NOT FOR GENERAL USE.

    WCL = WAYBACK_COMMITS_LOG_LOCAL_PC if pc else WAYBACK_COMMITS_LOG_LOCAL
    WCR = WAYBACK_COMMITS_LOG_REMOTE_PC if pc else WAYBACK_COMMITS_LOG_REMOTE
    WMUT = WAYBACK_MANIFEST_URL_TEMPLATE_PC if pc else WAYBACK_MANIFEST_URL_TEMPLATE

    if target_version == 0:  # fetch from server
        url = urljoin(GKMAS_API_URL_PC if pc else GKMAS_API_URL, str(base_revision))
        enc = _rget(url, headers=GKMAS_API_HEADER).content
        dec = AESCBCDecryptor(
            GKMAS_ONLINEPDB_KEY_PC if pc else GKMAS_ONLINEPDB_KEY, enc[:16]
        ).process(enc[16:])
        return GkmasManifest(pdbytes2dict(dec), base_revision, pc=pc)

    if _use_local_commits_log and Path(WCL).is_file():
        commits = _json_load(WCL)
    else:
        commits = _json_load(WCR)

    _target = GkmasManifestVersion(
        int(target_version)
        if isinstance(target_version, int) or target_version.isdigit()
        else target_version
    )

    if str(_target) not in commits:
        raise ValueError(f"Manifest version {_target} not found in history.")
    url = WMUT.format(hash=commits[str(_target)], revision=base_revision)

    # we don't pass in pc=pc since the era will be overridden anyway
    manifest = GkmasManifest(_rget(url).json(), base_revision)
    assert (
        manifest.version.this.rev == _target.this.rev
    ), "Manifest version mismatch with commit history record."
    manifest.version.this.era = _target.this.era  # manual override
    if manifest.version.base.rev:
        manifest.version.base.era = _target.this.era  # tricky!
    return manifest


def load(src: PathArgtype, base_revision: int = 0, pc: bool = False) -> GkmasManifest:
    """
    Initializes a manifest from the given offline source.
    The protobuf referred to can be either encrypted or not.
    Also supports importing from JSON.

    Args:
        src (str | Path): Path to the manifest file.
            Can be the path to
            - an encrypted octocache (usually named 'octocacheevai'),
            - a decrypted protobuf, or
            - a JSON file exported from another manifest.
        base_revision (int) = 0: The revision number of the base manifest.
            **Must be manually specified if loading a diff generated
            by GkmasObjectManager older than or equal to v0.4-beta.**
        pc (bool): Whether we're initializing a PC manifest.
            Defaults to False (mobile).
    """

    try:
        return GkmasManifest(_json_load(src), base_revision, pc=pc)

    except JSONDecodeError:
        enc = Path(src).read_bytes()
        try:
            return GkmasManifest(pdbytes2dict(enc), base_revision, pc=pc)
        except DecodeError:
            dec = AESCBCDecryptor(GKMAS_OCTOCACHE_KEY, GKMAS_OCTOCACHE_IV).process(enc)
            return GkmasManifest(
                pdbytes2dict(dec[16:]), base_revision, pc=pc
            )  # trim md5 hash
