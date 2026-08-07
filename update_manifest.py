"""
update_manifest.py
Script to fetch latest manifest and diff from server,
compatible with 'Update Manifest' workflow.
"""

import asyncio
import sys
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

from tqdm import tqdm

from GkmasObjectManager import GkmasManifest, fetch
from GkmasObjectManager.const import (
    WAYBACK_COMMITS_LOG_LOCAL,
    WAYBACK_OBJECTS_LOG_LOCAL,
)
from GkmasObjectManager.manifest.versioning import GkmasManifestVersion, str2version
from GkmasObjectManager.utils import _json_dump, _json_load, append_unity_suffix

# FUNCTION HIERARCHY:
# [main]
#   -> do_update
#       -> _export_diff_manifests
#           -> _export_diff_manifest
#       -> rebuild_log
#           -> _fetch_old_manifests
#               -> _fetch_old_manifest
#           -> _append_log
#               -> _sanitize_canon_repr
#   -> record_commit_hash


sort_dict = lambda d: dict(sorted(d.items(), key=lambda x: x[0]))


def _fetch_old_manifest(ver: str, prog: tqdm) -> GkmasManifest:

    manifest = fetch(ver, _use_local_commits_log=True)
    prog.update(1)
    return manifest


async def _fetch_old_manifests(vers: list[str]) -> list[GkmasManifest]:

    with tqdm(total=len(vers), desc="Fetching historical manifests") as prog:
        return await asyncio.gather(
            *[asyncio.to_thread(_fetch_old_manifest, ver, prog) for ver in vers]
        )


def _sanitize_canon_repr(canon_repr: dict, ver: GkmasManifestVersion) -> str:
    return "|".join(
        [
            str(ver.this),
            canon_repr["objectName"],
            canon_repr["md5"],
            str(canon_repr["size"]),
        ]
    )


def _append_log(log: dict, manifest: GkmasManifest) -> None:

    for obj in manifest.assetbundles:
        log["assetBundleList"][append_unity_suffix(obj.name)].append(
            _sanitize_canon_repr(obj.canon_repr, manifest.version)
        )

    for obj in manifest.resources:
        log["resourceList"][obj.name].append(
            _sanitize_canon_repr(obj.canon_repr, manifest.version)
        )


def rebuild_log(latest_manifest: GkmasManifest):
    print("Rebuilding wayback log...")

    new_version = latest_manifest.version
    log = {
        "latest_version": str(new_version),
        "assetBundleList": defaultdict(list),
        "resourceList": defaultdict(list),
        "urlFormat": latest_manifest.urlformat,
    }

    is_incremental = Path(WAYBACK_OBJECTS_LOG_LOCAL).exists()

    if is_incremental:
        old_log = _json_load(WAYBACK_OBJECTS_LOG_LOCAL)
        old_version = str2version(old_log["latest_version"])
        if not old_version < new_version:  # pylint doesn't like implicit >=
            return  # already up-to-date
        log["assetBundleList"] = defaultdict(list, old_log["assetBundleList"])
        log["resourceList"] = defaultdict(list, old_log["resourceList"])

    commits = _json_load(WAYBACK_COMMITS_LOG_LOCAL)
    vers = map(str2version, commits.keys())
    if is_incremental:
        vers = filter(lambda v: not v < old_version, vers)
        # Manifest #old_version (equal case) must still be fetched for diff
    vers = list(map(str, sorted(vers)))

    manifests = asyncio.run(_fetch_old_manifests(vers))
    if manifests[-1].version == new_version:
        manifests.pop()  # remove the last duplicate
    manifests.append(latest_manifest)

    # in incremental update, everything is diff'ed
    # and update starts from [1]-[0], so [0] is skipped
    if not is_incremental:
        _append_log(log, manifests[0])
    for i in tqdm(range(1, len(manifests)), desc="Appending manifest diffs"):
        _append_log(log, manifests[i] - manifests[i - 1])

    log["assetBundleList"] = sort_dict(log["assetBundleList"])
    log["resourceList"] = sort_dict(log["resourceList"])
    _json_dump(log, WAYBACK_OBJECTS_LOG_LOCAL)


def _export_diff_manifest(path: Path, rev: int) -> None:
    fetch(base_revision=rev).export(path / f"v{rev:04}.json", force_overwrite=True)


async def _export_diff_manifests(path: Path, revs: list[int]) -> None:

    await asyncio.gather(
        *[asyncio.to_thread(_export_diff_manifest, path, rev) for rev in revs]
    )


def do_update(path: Path) -> bool:
    """Check for manifest update from server and optionally update all diff versions."""
    print("Checking for manifest update...")

    m_remote = fetch()
    ver_remote = m_remote.version
    ver_local = str2version((path / "LATEST_VERSION").read_text())

    if ver_remote == ver_local:
        print("No update available.")
        return False

    # Only write to file after sanity check;
    # this number is used to construct commit message in workflow.
    print(f"Found new manifest version: {ver_remote} (local: {ver_local})")
    (path / "LATEST_VERSION").write_text(str(ver_remote))

    m_remote.export(path / "v0000.json", force_overwrite=True)
    asyncio.run(_export_diff_manifests(path, list(range(1, ver_remote.this.rev))))

    rebuild_log(m_remote)

    return True


def record_commit_hash(ver_hash: str) -> bool:
    """Record a new commit hash from the last manifest update into wayback_commits.json."""

    ver, commit_hash = ver_hash.split("|")

    commits = _json_load(WAYBACK_COMMITS_LOG_LOCAL)
    commits[ver] = commit_hash
    _json_dump(sort_dict(commits), WAYBACK_COMMITS_LOG_LOCAL)

    return True


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument(
        "--record-commit-hash",
        type=str,
        help='record a new commit hash for a version (requires "<version>|<commit_hash>" format)',
    )
    args = parser.parse_args()

    if args.record_commit_hash:
        sys.exit(not record_commit_hash(args.record_commit_hash))

    HAS_UPDATE = do_update(Path("manifests"))
    sys.exit(not (HAS_UPDATE))
