"""
wayback.py
Interface with the "wayback machine", i.e. the object history log.
"""

import asyncio
import re
from pathlib import Path
from typing import Optional

from rich.progress import BarColumn, Progress, TextColumn

from GkmasObjectManager.const import WAYBACK_OBJECTS_LOG_REMOTE
from GkmasObjectManager.object import GkmasAssetBundle, GkmasResource
from GkmasObjectManager.utils import _json_load, nocache

ObjectClass = GkmasAssetBundle | GkmasResource


class WaybackEntry:

    name: str
    history: list[ObjectClass]

    def __init__(self, info: dict, base_class: ObjectClass, url_template: str):
        self.name = info["name"]
        self.history = []
        for entry in info["history"]:
            rev, objectName, md5, size, dependencies = entry.split("|")
            stem, ext = Path(self.name).stem, Path(self.name).suffix
            ext = ext.removesuffix(".unity3d")
            self.history.append(
                base_class(
                    {
                        "id": -1,  # stripped when building wayback log for compatibility
                        "name": f"{stem}__v{int(rev):04d}{ext}",
                        "objectName": objectName,
                        "md5": md5,
                        "size": int(size),
                        "dependencies": (
                            list(map(int, dependencies.split(",")))
                            if dependencies
                            else []
                        ),
                    },
                    url_template,
                    _deobf_key=self.name,
                )
            )

    def __repr__(self) -> str:
        return f"<WaybackEntry '{self.name}' with {len(self.history)} revisions>"


class WaybackEntryList:

    infos: list[dict]
    base_class: ObjectClass
    url_template: str

    _entries: list[Optional[WaybackEntry]]
    _name_idx: dict[str, int]

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return name.removesuffix(".unity3d")

    def __init__(self, infos: list[dict], base_class: ObjectClass, url_template: str):

        self.infos = infos
        self.base_class = base_class
        self.url_template = url_template

        self._entries = [None] * len(infos)
        self._name_idx = {
            self._sanitize_name(info["name"]): i for i, info in enumerate(infos)
        }

    def __repr__(self) -> str:
        return f"<WaybackEntryList of {len(self.infos)} {self.base_class.__name__}'s>"

    def _get_entry(self, idx: int) -> WaybackEntry:
        if self._entries[idx] is None:
            self._entries[idx] = WaybackEntry(
                self.infos[idx], self.base_class, self.url_template
            )
        return self._entries[idx]

    def __getitem__(self, key: str) -> WaybackEntry:
        idx = self._name_idx[self._sanitize_name(key)]
        return self._get_entry(idx)

    def __iter__(self):
        for i in range(len(self.infos)):
            yield self._get_entry(i)

    def __len__(self) -> int:
        return len(self.infos)

    def __contains__(self, key: str) -> bool:
        return self._sanitize_name(key) in self._name_idx


class WaybackMachine:

    revision: int
    assetbundles: WaybackEntryList
    resources: WaybackEntryList

    def __init__(self):
        log = _json_load(WAYBACK_OBJECTS_LOG_REMOTE)
        self.revision = log["latest_revision"]
        self.assetbundles = WaybackEntryList(
            log["assetBundleList"], GkmasAssetBundle, log["urlFormat"]
        )
        self.resources = WaybackEntryList(
            log["resourceList"], GkmasResource, log["urlFormat"]
        )

    def __repr__(self) -> str:
        return f"<WaybackMachine revision {self.revision} with {len(self.assetbundles)} assetbundles and {len(self.resources)} resources>"

    def __getitem__(self, key: str) -> WaybackEntry:
        if key in self.assetbundles:
            return self.assetbundles[key]
        elif key in self.resources:
            return self.resources[key]
        else:
            raise KeyError(f"No entry with name '{key}'.")

    def __iter__(self):
        for ab in self.assetbundles:
            yield ab
        for res in self.resources:
            yield res

    def __len__(self) -> int:
        return len(self.assetbundles) + len(self.resources)

    def __contains__(self, key: str) -> bool:
        return key in self.assetbundles or key in self.resources

    def search(self, criterion: str, ascending: bool = True) -> list[WaybackEntry]:
        matches = filter(
            lambda s: re.match(criterion, s.name, flags=re.IGNORECASE) is not None,
            list(self),
        )
        return sorted(matches, key=lambda x: x.name, reverse=not ascending)

    @nocache
    def download_old_revisions(self, *criteria: str, **kwargs):
        entries = self.search("|".join(criteria))
        asyncio.run(self._dispatch(entries, **kwargs))

    async def _dispatch(self, entries: list[WaybackEntry], **kwargs):

        progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        )

        tasks = [
            asyncio.create_task(
                asyncio.to_thread(
                    obj.download,
                    progress=progress,
                    task_id=progress.add_task(obj.name, visible=False),
                    **kwargs,  # if not empty, broadcast to all tasks
                )
            )
            for entry in entries
            for obj in entry.history[:-1]
        ]

        progress.start()
        await asyncio.gather(*tasks)
        progress.stop()
