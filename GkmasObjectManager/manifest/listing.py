"""
listing.py
"Object list" class holding a list of dictionaries,
optimized for indexing and comparison.
"""

from ..const import (
    OBJLIST_ID_FIELD,
    OBJLIST_NAME_FIELD,
)

from typing import Union


class GkmasObjectList:
    """
    A list of assetbundle/resource metadata, optimized for indexing and comparison.
    Implemented as listing utility wrappers around a list of dictionaries.

    Methods:
        __sub__(other: GkmasObjectList) -> GkmasObjectList:
            Subtracts another object list from this one.
            Returns the list of elements unique to 'self'.
        rip_field(targets: list) -> GkmasObjectList:
            Removes selected fields from all dictionaries.
        diff(other: GkmasObjectList, ignored_fields: list) -> GkmasObjectList:
            Compares two object lists while ignoring selected fields,
            but **retains all fields** in the reconstructed output.
    """

    def __init__(self, infos: list, base_class: object):
        infos.sort(key=lambda x: x[OBJLIST_ID_FIELD])
        self.infos = infos
        self.base_class = base_class
        self._objects = [None] * len(infos)
        self._id_idx = {info[OBJLIST_ID_FIELD]: i for i, info in enumerate(infos)}
        self._name_idx = {info[OBJLIST_NAME_FIELD]: i for i, info in enumerate(infos)}
        # 'self._*_idx' are int/str -> int lookup tables

    def __repr__(self):
        return f"<GkmasObjectList of {len(self.infos)} {self.base_class.__name__}'s>"

    def __getitem__(self, key: Union[int, str]) -> object:

        if isinstance(key, int):
            idx = self._id_idx[key]
        elif isinstance(key, str):
            idx = self._name_idx[key]
        else:
            raise TypeError  # just in case, should never reach here

        if self._objects[idx] is None:
            self._objects[idx] = self.base_class(self.infos[idx])

        return self._objects[idx]

    def __iter__(self):
        for info in self.infos:
            yield self.base_class(info)

    def __len__(self):
        return len(self.infos)

    def __contains__(self, key: str) -> bool:
        return key in self._name_idx
        # 'if <numerical ID> in self' is nonsensical

    def __sub__(self, other: "GkmasObjectList") -> "GkmasObjectList":
        assert self.base_class == other.base_class
        canon_reprs = []
        for entry in self:
            try:
                this_repr = entry._get_canon_repr()
                other_repr = other[entry.name]._get_canon_repr()
            except KeyError:
                canon_reprs.append(this_repr)
                continue
            else:
                if this_repr != other_repr:
                    canon_reprs.append(this_repr)
        return GkmasObjectList(canon_reprs, self.base_class)

    def __add__(self, other: "GkmasObjectList") -> "GkmasObjectList":
        # 'other' is assumed to be newer, since revision is not accessible here
        assert self.base_class == other.base_class
        mapped = {entry["id"]: entry for entry in self._get_canon_repr()}
        mapped.update({entry["id"]: entry for entry in other._get_canon_repr()})  # hack
        return GkmasObjectList(list(mapped.values()), self.base_class)

    def _get_canon_repr(self):
        """
        [INTERNAL] Returns the JSON-compatible "canonical" representation of the object list.
        """
        return [entry._get_canon_repr() for entry in self]
