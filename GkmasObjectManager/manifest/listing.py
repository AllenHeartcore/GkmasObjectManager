"""
listing.py
"Object list" class holding a list of dictionaries,
optimized for indexing and comparison.
"""

from typing import Union


class GkmasObjectList:
    """
    A list of assetbundle/resource metadata, optimized for indexing and comparison.
    Implemented as listing utility wrappers around a list of dictionaries.

    Attributes:
        infos (list): List of dictionaries containing metadata for each object.
        base_class (object): The class that will be instantiated for each object.
        url_template (str): URL template for fetching the objects.
            Only used when instantiating objects from the list.
    """

    def __init__(self, infos: list[dict], base_class: object, url_template: str):
        infos.sort(key=lambda x: x["id"])

        self.infos = infos
        self.base_class = base_class
        self.url_template = url_template

        self._objects = [None] * len(infos)
        self._id_idx = {info["id"]: i for i, info in enumerate(infos)}
        self._name_idx = {info["name"]: i for i, info in enumerate(infos)}
        # 'self._*_idx' are int/str -> int lookup tables

    def __repr__(self) -> str:
        return f"<GkmasObjectList of {len(self.infos)} {self.base_class.__name__}'s>"

    def _get_object(self, idx: int) -> object:
        # necessary for enabling cache everywhere
        if self._objects[idx] is None:
            self._objects[idx] = self.base_class(self.infos[idx], self.url_template)
        return self._objects[idx]

    def __getitem__(self, key: Union[int, str]) -> object:

        if isinstance(key, int):
            idx = self._id_idx[key]
        elif isinstance(key, str):
            idx = self._name_idx[key]
        else:
            raise TypeError  # just in case, should never reach here

        return self._get_object(idx)

    def __iter__(self):
        for i in range(len(self.infos)):
            yield self._get_object(i)

    def __len__(self) -> int:
        return len(self.infos)

    def __contains__(self, key: str) -> bool:
        return key in self._name_idx
        # 'if <numerical ID> in self' is nonsensical

    def __sub__(self, other: "GkmasObjectList") -> "GkmasObjectList":
        assert self.base_class == other.base_class
        canon_reprs = []
        for entry in self:
            this_repr = entry._get_canon_repr()
            try:
                other_repr = other[entry.name]._get_canon_repr()
            except KeyError:
                canon_reprs.append(this_repr)
            else:
                if this_repr != other_repr:
                    canon_reprs.append(this_repr)
        return GkmasObjectList(canon_reprs, self.base_class, self.url_template)

    def __add__(self, other: "GkmasObjectList") -> "GkmasObjectList":
        # 'other' is assumed to be newer, since revision is not accessible here
        assert self.base_class == other.base_class
        mapped = {entry["id"]: entry for entry in self._get_canon_repr()}
        mapped.update({entry["id"]: entry for entry in other._get_canon_repr()})  # hack
        return GkmasObjectList(
            list(mapped.values()), self.base_class, self.url_template
        )

    def _get_canon_repr(self) -> list[dict]:
        """
        [INTERNAL] Returns the JSON-compatible "canonical" representation of the object list.
        """
        return [entry._get_canon_repr() for entry in self]
