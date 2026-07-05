"""
update_manifest.py
Script to fetch latest manifest and diff from server,
compatible with 'Update Manifest' workflow.
"""

import asyncio
import sys
from argparse import ArgumentParser
from pathlib import Path

from tqdm import tqdm

from GkmasObjectManager import GkmasManifest, fetch
from GkmasObjectManager.const import (
    WAYBACK_COMMITS_LOG_LOCAL,
    WAYBACK_OBJECTS_LOG_LOCAL,
)
from GkmasObjectManager.utils import _json_dump, _json_load

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


def _fetch_old_manifest(rev: int, prog: tqdm) -> GkmasManifest:

    manifest = fetch(rev, _use_local_commits_log=True)
    prog.update(1)
    return manifest


async def _fetch_old_manifests(revs: list[int]) -> list[GkmasManifest]:

    with tqdm(total=len(revs), desc="Fetching historical manifests") as prog:
        return await asyncio.gather(
            *[asyncio.to_thread(_fetch_old_manifest, rev, prog) for rev in revs]
        )


def _sanitize_canon_repr(canon_repr: dict, rev: int) -> str:
    return "|".join(
        [
            f"{rev:04d}",
            canon_repr["objectName"],
            canon_repr["md5"],
            str(canon_repr["size"]),
            ",".join(map(str, canon_repr.get("dependencies", []))),
        ]
    )


def _append_log(log: dict, manifest: GkmasManifest) -> None:

    for obj in manifest.assetbundles:
        log["assetBundleList"][obj.name].append(
            _sanitize_canon_repr(obj.canon_repr, manifest.revision.this)
        )

    for obj in manifest.resources:
        log["resourceList"][obj.name].append(
            _sanitize_canon_repr(obj.canon_repr, manifest.revision.this)
        )


def rebuild_log(latest_manifest: GkmasManifest):
    print("Rebuilding wayback log...")

    log = {
        "latest_revision": latest_manifest.revision.canon_repr,
        "assetBundleList": {obj.name: [] for obj in latest_manifest.assetbundles},
        "resourceList": {obj.name: [] for obj in latest_manifest.resources},
        "urlFormat": latest_manifest.urlformat,
    }

    is_incremental = Path(WAYBACK_OBJECTS_LOG_LOCAL).exists()

    if not is_incremental:
        old_revision = -1
    else:
        old_log = _json_load(WAYBACK_OBJECTS_LOG_LOCAL)
        old_revision = int(old_log["latest_revision"])
        if old_revision >= latest_manifest.revision.this:
            return  # already up-to-date
        log["assetBundleList"] = old_log["assetBundleList"]
        log["resourceList"] = old_log["resourceList"]

    commits = _json_load(WAYBACK_COMMITS_LOG_LOCAL)
    revs = sorted([int(k) for k in commits.keys() if int(k) >= old_revision])
    # Manifest #old_revision must still be fetched for diff

    manifests = asyncio.run(_fetch_old_manifests(revs))
    if manifests[-1].revision == latest_manifest.revision:
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
    """Check for manifest update from server and optionally update all diff revisions."""
    print(f"Checking for manifest update...")

    m_remote = fetch()
    rev_remote = m_remote.revision.canon_repr
    rev_local = int((path / "LATEST_REVISION").read_text())

    if rev_remote == rev_local:
        print("No update available.")
        return False

    # Only write to file after sanity check;
    # this number is used to construct commit message in workflow.
    print(f"Found new manifest revision: {rev_remote} (local: {rev_local})")
    (path / "LATEST_REVISION").write_text(str(rev_remote))

    m_remote.export(path / "v0000.json", force_overwrite=True)
    asyncio.run(_export_diff_manifests(path, list(range(1, rev_remote))))

    rebuild_log(m_remote)

    return True


def record_commit_hash(rev_hash: str) -> bool:
    """Record a new commit hash from the last manifest update into wayback_commits.json."""

    rev, commit_hash = rev_hash.split("|")

    commits = _json_load(WAYBACK_COMMITS_LOG_LOCAL)
    commits[rev] = commit_hash
    commits = sort_dict({int(k): v for k, v in commits.items()})
    _json_dump(commits, WAYBACK_COMMITS_LOG_LOCAL)

    return True


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument(
        "--record-commit-hash",
        type=str,
        help='record a new commit hash for a revision (requires "<revision>|<commit_hash>" format)',
    )
    args = parser.parse_args()

    if args.record_commit_hash:
        sys.exit(not record_commit_hash(args.record_commit_hash))

    HAS_UPDATE = do_update(Path("manifests"))
    sys.exit(not (HAS_UPDATE))
