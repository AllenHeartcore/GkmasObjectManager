"""
wayback.py
Interface with the "wayback machine", i.e. the object history log.
"""

import re
from pathlib import Path
from typing import Optional

from GkmasObjectManager.const import WAYBACK_OBJECTS_LOG_REMOTE
from GkmasObjectManager.object import GkmasAssetBundle, GkmasResource
from GkmasObjectManager.utils import _json_load

ObjectClass = GkmasAssetBundle | GkmasResource


class WaybackEntry:

    id: int
    name: str
    history: list[ObjectClass]

    def __init__(self, info: dict, base_class: ObjectClass, url_template: str):
        self.id = info["id"]
        self.name = info["name"]
        self.history = []
        for entry in info["history"]:
            rev, objectName, md5, size, dependencies = entry.split("|")
            stem, ext = Path(self.name).stem, Path(self.name).suffix
            ext = ext.removesuffix(".unity3d")
            self.history.append(
                base_class(
                    {
                        "id": self.id,
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
        type_abbrev = "AB" if isinstance(self.history[-1], GkmasAssetBundle) else "RS"
        return f"<WaybackEntry {type_abbrev}[{self.id:05}] '{self.name}' with {len(self.history)} revisions>"


class WaybackEntryList:

    infos: list[dict]
    base_class: ObjectClass
    url_template: str

    _entries: list[Optional[WaybackEntry]]
    _id_idx: dict[int, int]
    _name_idx: dict[str, int]

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return name.removesuffix(".unity3d")

    def __init__(self, infos: list[dict], base_class: ObjectClass, url_template: str):
        infos.sort(key=lambda x: x["id"])

        self.infos = infos
        self.base_class = base_class
        self.url_template = url_template

        self._entries = [None] * len(infos)
        self._id_idx = {info["id"]: i for i, info in enumerate(infos)}
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

    def __getitem__(self, key: int | str) -> WaybackEntry:

        if isinstance(key, int):
            idx = self._id_idx[key]
        elif isinstance(key, str):
            idx = self._name_idx[self._sanitize_name(key)]
        else:
            raise TypeError

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

    def search(
        self,
        criterion: str,
        by_name: bool = True,
        ascending: bool = True,
    ) -> list[WaybackEntry]:
        matches = filter(
            lambda s: re.match(criterion, s.name, flags=re.IGNORECASE) is not None,
            list(self),
        )
        return sorted(
            matches,
            key=lambda x: x.name if by_name else x.id,
            reverse=not ascending,
        )

    def download_old_revisions(self, criterion: str, output_dir: str, **kwargs):
        for entry in self.search(criterion):
            for obj in entry.history[:-1]:
                obj.download(output_dir, **kwargs)

    @nocache
    def download(self, *criteria: str, **kwargs):
        """
        Downloads the regex-specified assetbundles/resources to the specified path.

        Args:
            *criteria (str): Regex patterns of assetbundle/resource names.
            path (str | Path) = DEFAULT_DOWNLOAD_PATH: A directory to which the objects are downloaded.
                *WARNING: Behavior is undefined if the path points to an definite file (with extension).*
            categorize (bool) = True: Whether to categorize downloaded objects into subdirectories.
                If False, all objects are downloaded to the specified 'path' in a flat structure.
        """

        if "preset" in kwargs:
            self.download_preset(kwargs.pop("preset"))
            return

        if not criteria:
            logger.warning(
                "No criteria specified; download everything with download_all() instead"
            )
            return

        objects = self.search("|".join(criteria))

        if not objects:
            logger.warning("No objects matched the criteria, aborted")
            return

        asyncio.run(self._dispatch(objects, **kwargs))

    async def _dispatch(
        self,
        obj_kw: list[ObjectClass | Tuple[ObjectClass, dict]],
        **kwargs,
    ):
        """
        [INTERNAL] Dispatches a list of object-kwargs pairs to async download tasks.
        """

        # if "obj_kw" is a list of objects, append empty kwargs
        if not isinstance(obj_kw[0], tuple):
            obj_kw = [(obj, {}) for obj in obj_kw]

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
                    task_id=progress.add_task(obj._idname, visible=False),
                    **kw,
                    **kwargs,  # if not empty, broadcast to all tasks
                )
            )
            for obj, kw in obj_kw
        ]

        progress.start()
        await asyncio.gather(*tasks)
        progress.stop()
