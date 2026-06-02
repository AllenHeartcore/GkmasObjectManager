"""
wayback.py
Interface with the "wayback machine", i.e. the object history log.
"""

import re
from typing import Optional

from GkmasObjectManager.object import GkmasAssetBundle, GkmasResource

ObjectClass = GkmasAssetBundle | GkmasResource


class WaybackEntryList:

    infos: list[dict]
    base_class: ObjectClass
    url_template: str

    _entries: list[Optional[ObjectClass]]
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

    def _get_entry(self, idx: int) -> ObjectClass:
        if self._entries[idx] is None:
            self._entries[idx] = self.base_class(self.infos[idx], self.url_template)
        return self._entries[idx]

    def __getitem__(self, key: int | str) -> ObjectClass:

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
    urlformat: str

    def __init__(self, log: dict):

        self.revision = log["revision"]
        self.assetbundles = WaybackEntryList(
            log["assetBundleList"], GkmasAssetBundle, log["urlFormat"]
        )
        self.resources = WaybackEntryList(
            log["resourceList"], GkmasResource, log["urlFormat"]
        )

        self.urlformat = log["urlFormat"]

    def __repr__(self) -> str:
        return f"<WaybackMachine revision {self.revision} with {len(self.assetbundles)} assetbundles and {len(self.resources)} resources>"

    def __getitem__(self, key: str) -> ObjectClass:
        try:
            return self.assetbundles[key]
        except KeyError:
            return self.resources[key]

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
    ) -> list[ObjectClass]:
        matches = filter(
            lambda s: re.match(criterion, s.name, flags=re.IGNORECASE) is not None,
            list(self),
        )
        return sorted(
            matches,
            key=lambda x: x.name if by_name else x.id,
            reverse=not ascending,
        )
