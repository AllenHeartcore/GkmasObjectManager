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
    WAYBACK_COMMITS_DATABASE_LOCAL,
    WAYBACK_INDEX_DATABASE_LOCAL,
)
from GkmasObjectManager.utils import _json_dump, _json_load


def _fetch_old_manifest(rev: int, prog: tqdm) -> GkmasManifest:

    manifest = fetch(rev, _use_local_commits_database=True)
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


def _append_index(index: dict, manifest: GkmasManifest) -> None:

    for obj in manifest.assetbundles:
        ab_id = index["ab_id_lookup"][obj.id]
        index["assetBundleList"][ab_id]["history"].append(
            _sanitize_canon_repr(obj.canon_repr, manifest.revision.this)
        )

    for obj in manifest.resources:
        res_id = index["res_id_lookup"][obj.id]
        index["resourceList"][res_id]["history"].append(
            _sanitize_canon_repr(obj.canon_repr, manifest.revision.this)
        )


def rebuild_index(latest_manifest: GkmasManifest):
    print("Rebuilding wayback index...")

    index = {
        "latest_revision": latest_manifest.revision.canon_repr,
        "assetBundleList": [
            {"id": obj.id, "name": obj.name, "history": []}
            for obj in latest_manifest.assetbundles
        ],
        "resourceList": [
            {"id": obj.id, "name": obj.name, "history": []}
            for obj in latest_manifest.resources
        ],
        "ab_id_lookup": {
            obj.id: idx for idx, obj in enumerate(latest_manifest.assetbundles)
        },
        "res_id_lookup": {
            obj.id: idx for idx, obj in enumerate(latest_manifest.resources)
        },
        "urlFormat": latest_manifest.urlformat,
    }

    is_incremental = Path(WAYBACK_INDEX_DATABASE_LOCAL).exists()

    if not is_incremental:
        old_revision = -1
    else:
        old_index = _json_load(WAYBACK_INDEX_DATABASE_LOCAL)
        old_revision = int(old_index["latest_revision"])
        if old_revision >= latest_manifest.revision.this:
            return  # already up-to-date

        # patch index with history **in-place**
        for old_entry in old_index["assetBundleList"]:
            entry_idx = index["ab_id_lookup"][old_entry["id"]]
            entry = index["assetBundleList"][entry_idx]  # is a pointer
            assert entry["name"] == old_entry["name"]
            entry["history"] = old_entry["history"]
        for old_entry in old_index["resourceList"]:
            entry_idx = index["res_id_lookup"][old_entry["id"]]
            entry = index["resourceList"][entry_idx]
            assert entry["name"] == old_entry["name"]
            entry["history"] = old_entry["history"]

    commits = _json_load(WAYBACK_COMMITS_DATABASE_LOCAL)
    revs = sorted([int(k) for k in commits.keys() if int(k) >= old_revision])
    # Manifest #old_revision must still be fetched for diff

    manifests = asyncio.run(_fetch_old_manifests(revs))
    manifests.append(latest_manifest)

    for i in tqdm(range(len(manifests)), desc="Building wayback index"):
        if i == 0:
            if not is_incremental:
                _append_index(index, manifests[i])
            # in incremental update, everything is diff'ed
            # and update starts from [1]-[0], so [0] is skipped
        else:
            _append_index(index, manifests[i] - manifests[i - 1])

    del index["ab_id_lookup"]
    del index["res_id_lookup"]
    _json_dump(index, WAYBACK_INDEX_DATABASE_LOCAL)


def _export_diff_manifest(path: Path, rev: int, pc: bool) -> None:
    fetch(base_revision=rev, pc=pc).export(
        path / f"v{rev:04}.json", force_overwrite=True
    )


async def _export_diff_manifests(path: Path, revs: list[int], pc: bool) -> None:

    await asyncio.gather(
        *[asyncio.to_thread(_export_diff_manifest, path, rev, pc) for rev in revs]
    )


def do_update(path: Path, pc: bool = False) -> bool:
    """Check for manifest update from server and optionally update all diff revisions."""
    print(f"Checking for {'PC' if pc else 'mobile'} manifest update...")

    m_remote = fetch(pc=pc)
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
    asyncio.run(_export_diff_manifests(path, list(range(1, rev_remote)), pc))

    if not pc:
        rebuild_index(m_remote)

    return True


def record_commit_hash(rev_hash: str) -> bool:
    """Record a new commit hash from the last manifest update into wayback_commits.json."""

    rev, commit_hash = rev_hash.split("|")

    commits = _json_load(WAYBACK_COMMITS_DATABASE_LOCAL)
    commits[rev] = commit_hash
    commits = dict(sorted(commits.items(), key=lambda x: int(x[0])))
    _json_dump(commits, WAYBACK_COMMITS_DATABASE_LOCAL)

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
    HAS_UPDATE_PC = do_update(Path("manifests_pc"), pc=True)
    sys.exit(not (HAS_UPDATE or HAS_UPDATE_PC))  # avoids short-circuiting
