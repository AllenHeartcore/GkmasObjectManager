"""
manifest.py
Manifest decryption, exporting, and object downloading.
"""

import re
from typing import Optional

from GkmasObjectManager.object import GkmasAssetBundle, GkmasResource
from GkmasObjectManager.rich import Logger
from GkmasObjectManager.manifest.listing import GkmasObjectList
from GkmasObjectManager.manifest.revision import GkmasManifestRevision

ObjectClass = GkmasAssetBundle | GkmasResource

# The logger would better be a global variable in the
# modular __init__.py, but Python won't allow me to
logger = Logger()


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

    infos: list[dict]
    base_class: ObjectClass
    url_template: str

    _objects: list[Optional[ObjectClass]]
    _id_idx: dict[int, int]
    _name_idx: dict[str, int]

    @staticmethod
    def _sanitize_name(name: str) -> str:
        # isolate this util as an undesirable accommodation for choosing to
        # include the suffix in object.assetbundle.name for now
        return name.removesuffix(".unity3d")

    def __init__(self, infos: list[dict], base_class: ObjectClass, url_template: str):
        infos.sort(key=lambda x: x["id"])

        self.infos = infos
        self.base_class = base_class
        self.url_template = url_template

        self._objects = [None] * len(infos)
        self._id_idx = {info["id"]: i for i, info in enumerate(infos)}
        self._name_idx = {
            self._sanitize_name(info["name"]): i for i, info in enumerate(infos)
        }
        # 'self._*_idx' are int/str -> int lookup tables

    def __repr__(self) -> str:
        return f"<GkmasObjectList of {len(self.infos)} {self.base_class.__name__}'s>"

    def _get_object(self, idx: int) -> ObjectClass:
        # necessary for enabling cache everywhere
        if self._objects[idx] is None:
            self._objects[idx] = self.base_class(self.infos[idx], self.url_template)
        return self._objects[idx]

    def __getitem__(self, key: int | str) -> ObjectClass:

        if isinstance(key, int):
            idx = self._id_idx[key]
        elif isinstance(key, str):
            idx = self._name_idx[self._sanitize_name(key)]
        else:
            raise TypeError  # just in case, should never reach here

        return self._get_object(idx)

    def __iter__(self):
        for i in range(len(self.infos)):
            yield self._get_object(i)

    def __len__(self) -> int:
        return len(self.infos)

    def __contains__(self, key: str) -> bool:
        return self._sanitize_name(key) in self._name_idx
        # 'if <numerical ID> in self' is nonsensical


class GkmasManifest:
    """
    A GKMAS manifest, containing info about assetbundles and resources.

    Attributes:
        revision (GkmasManifestRevision): Manifest revision this-diff-base (see revision.py).
        assetbundles (GkmasObjectList): List of assetbundle *info dictionaries*.
        resources (GkmasObjectList): List of resource *info dictionaries*.
        urlformat (str): URL format for downloading assetbundles/resources.

    Methods:
        export(path: str | Path) -> None:
            Exports the manifest as ProtoDB, JSON, and/or CSV to the specified path.
        search(criterion: str) -> list:
            Searches the manifest for objects with names *fully* matching the specified criterion.
        download(
            *criteria: str,
            path: str | Path = DEFAULT_DOWNLOAD_PATH,
            categorize: bool = True,
            **kwargs,
        ) -> None:
            Downloads the regex-specified assetbundles/resources to the specified path.
        download_preset(preset_filename: str) -> None:
            Downloads by a predefined preset (see examples in presets/).
        download_all_assetbundles(**kwargs) -> None
        download_all_resources(**kwargs) -> None
        download_all(**kwargs) -> None
    """

    revision: GkmasManifestRevision
    assetbundles: GkmasObjectList
    resources: GkmasObjectList
    urlformat: str

    def __init__(self, jdict: dict, base_revision: int = 0):
        """
        [INTERNAL] Initializes a manifest from the given JSON dictionary.

        Args:
            jdict (dict): JSON-serialized dictionary extracted from protobuf.
                Must contain 'revision' and 'urlFormat' fields.
                May contain 'assetBundleList' and 'resourceList'.
            base_revision (int) = 0: The revision number of the base manifest.
                Manually specified when loading a diff, at which case
                a warning of conflict is raised if jdict['revision'] is already a tuple.
        """

        revision = jdict["revision"]  # not jdict.get() to enforce presence
        if isinstance(revision, int):
            revision = (revision, 0)
        if base_revision != 0:  # leave negative base handling to the Revision class
            if base_revision != revision[1] != 0:  # equivalent to a 2-AND
                logger.warning(
                    f"Overriding detected base revision v{revision[1]} with specified v{base_revision}."
                )
            revision = (revision[0], base_revision)  # proceed anyway

        try:  # instantiate from JSON
            self.revision = GkmasManifestRevision(*revision)
            self.assetbundles = GkmasObjectList(
                jdict.get("assetBundleList", []),  # might be empty in recent diffs
                GkmasAssetBundle,
                jdict["urlFormat"],
            )
            self.resources = GkmasObjectList(
                jdict.get("resourceList", []),  # same as above ^
                GkmasResource,
                jdict["urlFormat"],
            )
        except TypeError:  # instantiate from diff, skip type conversion
            self.revision = jdict["revision"]
            self.assetbundles = jdict["assetBundleList"]  # won't be missing since ...
            self.resources = jdict["resourceList"]  # this is constructed internally

        self.urlformat = jdict["urlFormat"]
        # 'jdict' is then discarded and losslessly reconstructed at export

    def __repr__(self) -> str:
        return f"<GkmasManifest revision {self.revision} with {len(self.assetbundles)} assetbundles and {len(self.resources)} resources>"

    def __getitem__(self, key: str) -> ObjectClass:
        try:
            return self.assetbundles[key]
        except KeyError:
            return self.resources[key]
            # any more KeyError's are raised as is

    def __iter__(self):
        for ab in self.assetbundles:
            yield ab
        for res in self.resources:
            yield res

    def __len__(self) -> int:
        return len(self.assetbundles) + len(self.resources)

    def __contains__(self, key: str) -> bool:
        return key in self.assetbundles or key in self.resources
        # could also try self[key]

    def search(
        self,
        criterion: str,
        by_name: bool = True,
        ascending: bool = True,
    ) -> list[ObjectClass]:
        """
        Searches the manifest for objects matching the specified criterion.
        Returns a list of objects.

        Args:
            criterion (str): Regex pattern of object names.
        """

        # This will be called by frontend; we instantiate here to make ID's visible.
        matches = filter(
            lambda s: re.match(criterion, s.name, flags=re.IGNORECASE) is not None,
            list(self),
        )
        return sorted(
            matches,
            key=lambda x: x.name if by_name else x.id,
            reverse=not ascending,
        )
