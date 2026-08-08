"""
manifest.py
Manifest decryption, exporting, and object downloading.
"""

from pathlib import Path

from google.protobuf.json_format import ParseError

from ..const import PathArgtype
from ..object import GkmasAssetBundle, GkmasResource
from ..rich import Logger
from ..utils import _json_dump
from .listing import GkmasObjectList
from .octodb_pb2 import dict2pdbytes
from .versioning import GkmasManifestVersion

ObjectClass = GkmasAssetBundle | GkmasResource

# The logger would better be a global variable in the
# modular __init__.py, but Python won't allow me to
logger = Logger()


class GkmasManifest:
    """
    A GKMAS manifest, containing info about assetbundles and resources.

    Attributes:
        version (GkmasManifestVersion): Manifest version this-diff-base (see versioning.py).
        assetbundles (GkmasObjectList): List of assetbundle *info dictionaries*.
        resources (GkmasObjectList): List of resource *info dictionaries*.
        urlformat (str): URL format for downloading assetbundles/resources.

    Methods:
        export(path: str | Path) -> None:
            Exports the manifest as ProtoDB and/or JSON to the specified path.
        search(*criteria: str) -> list:
            Searches the manifest for objects with names *fully* matching the specified criteria.
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

    version: GkmasManifestVersion
    assetbundles: GkmasObjectList
    resources: GkmasObjectList
    urlformat: str

    def __init__(self, jdict: dict, base_revision: int = 0, pc: bool = False):
        """
        [INTERNAL] Initializes a manifest from the given JSON dictionary.

        Args:
            jdict (dict): JSON-serialized dictionary extracted from protobuf.
                Must contain 'revision' and 'urlFormat' fields.
                May contain 'assetBundleList' and 'resourceList'.
            base_revision (int) = 0: The revision number of the base manifest.
                Manually specified when loading a diff, at which case
                a warning of conflict is raised if jdict['revision'] is already a tuple.
            pc (bool): Whether we're initializing a PC manifest.
                Defaults to False (mobile).
                Solely affects the era of manifest version.
        """

        revision = jdict["revision"]  # not jdict.get() to enforce presence
        if isinstance(revision, GkmasManifestVersion):
            # instantiate from diff, skip type conversion
            self.version = revision
            self.assetbundles = jdict["assetBundleList"]  # won't be missing since ...
            self.resources = jdict["resourceList"]  # this is constructed internally
            self.urlformat = jdict["urlFormat"]
            return

        if isinstance(revision, int):
            revision = (revision, 0)
        if base_revision != 0:  # leave negative base handling to the Version class
            if base_revision != revision[1] != 0:  # equivalent to a 2-AND
                logger.warning(
                    f"Overriding detected base revision rev{revision[1]} with specified rev{base_revision}."
                )
            revision = (revision[0], base_revision)  # proceed anyway

        # instantiate from JSON
        self.version = GkmasManifestVersion(*revision, pc=pc)
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
        self.urlformat = jdict["urlFormat"]
        # 'jdict' is then discarded and losslessly reconstructed at export

    def __repr__(self) -> str:
        return f"<GkmasManifest version {self.version} with {len(self.assetbundles)} assetbundles and {len(self.resources)} resources>"

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

    def __sub__(self, other: "GkmasManifest") -> "GkmasManifest":
        if self.version.this.era != other.version.this.era:
            logger.warning("Performing cross-era manifest diff, IDs are meaningless.")
        return GkmasManifest(
            {  # this is not a standard JSON dict, more like named arguments
                "revision": self.version - other.version,  # handles sanity check
                "assetBundleList": self.assetbundles - other.assetbundles,
                "resourceList": self.resources - other.resources,
                "urlFormat": self.urlformat,
                # always override with the higher revision, in case this ever differs
            }
        )

    def __add__(self, other: "GkmasManifest") -> "GkmasManifest":
        if self.version.this.era != other.version.this.era:
            logger.warning("Performing cross-era manifest patch, IDs are meaningless.")
        new_version = self.version + other.version
        a, b = (
            (self, other) if new_version.this == other.version.this else (other, self)
        )  # 'b' must be newer; this matters in list addition
        return GkmasManifest(
            {
                "revision": new_version,
                "assetBundleList": a.assetbundles + b.assetbundles,
                "resourceList": a.resources + b.resources,
                "urlFormat": b.urlformat,
            }
        )

    @property
    def canon_repr(self) -> dict:
        """
        [INTERNAL] Returns the JSON-compatible "canonical" representation of the manifest.
        """
        return {
            "revision": self.version.canon_repr,
            "assetBundleList": self.assetbundles.canon_repr,
            "resourceList": self.resources.canon_repr,
            "urlFormat": self.urlformat,
        }

    # ------------ EXPORT ------------ #

    def export(
        self,
        path: PathArgtype,
        format: str = "infer",
        force_overwrite: bool = False,
    ):
        """
        Exports the manifest as ProtoDB and/or JSON to the specified path.
        This is a dispatcher method.

        Args:
            path (str | Path): A file path.
                The format is determined by the extension if 'format' is 'infer'.
                (All extensions other than .json are inferred
                as raw binary and therefore exported as ProtoDB, but
                a warning is issued if the extension is not .pdb.)
            format (str) = 'infer': The format to export.
                Should be one of 'pdb', 'json', or 'infer'.
            force_overwrite (bool) = False: Whether to overwrite the file if it already exists.
                Meant for exclusive use by update_manifest watcher.
        """

        path = Path(path)
        if path.exists() and not force_overwrite:
            logger.warning(f"{path} already exists, aborting")
            return

        if format == "infer":
            if path.suffix == ".pdb":
                format = "pdb"
            elif path.suffix == ".json":
                format = "json"
            else:
                logger.warning("Unrecognized file extension, defaulting to ProtoDB")
                format = "pdb"

        if format == "pdb":
            self._export_pdb(path)
        elif format == "json":
            self._export_json(path)
        else:
            logger.warning(f"Unrecognized format '{format}', aborted")
            # Could also be logger.error, but let's fail gracefully.
            # This check used to appear in the type hint, but then
            # this method would *silently* fail if the format was invalid.

    def _export_pdb(self, path: Path):
        """
        [INTERNAL] Writes raw protobuf bytes into the specified path.
        """

        if path.suffix != ".pdb":
            logger.warning("Attempting to write ProtoDB into a non-.pdb file")

        jdict = self.canon_repr
        if isinstance(jdict["revision"], tuple):
            logger.warning("Exporting a diff manifest as ProtoDB, base revision lost")
            jdict["revision"] = jdict["revision"][0]

        try:
            path.write_bytes(dict2pdbytes(jdict))
            logger.success(f"ProtoDB has been written into {path}")
        except ParseError:
            logger.error(f"Failed to write ProtoDB into {path}")

    def _export_json(self, path: Path):
        """
        [INTERNAL] Writes JSON-serialized dictionary into the specified path.
        """

        if path.suffix != ".json":
            logger.warning("Attempting to write JSON into a non-.json file")

        try:
            _json_dump(self.canon_repr, path)
            logger.success(f"JSON has been written into {path}")
        except TypeError:  # non-JSON-serializable object in dict
            logger.error(f"Failed to write JSON into {path}")
