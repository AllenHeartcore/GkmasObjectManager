"""
assetbundle.py
Unity asset bundle downloading, deobfuscation, and media extraction.
"""

from ..const import UNITY_SIGNATURE
from ..media import GkmasDummyMedia
from ..media.audio import GkmasUnityAudio
from ..media.image import GkmasUnityImage
from ..rich import ProgressReporter
from .deobfuscate import GkmasAssetBundleDeobfuscator
from .resource import GkmasResource


class GkmasAssetBundle(GkmasResource):
    """
    An assetbundle. Class inherits from GkmasResource.

    Attributes:
        All attributes from GkmasResource, plus
        name (str): Human-readable name, appended with '.unity3d'.
        crc (int): CRC checksum, unused for now (since scheme is unknown).

    Methods:
        download(
            path: Union[str, Path] = DEFAULT_DOWNLOAD_PATH,
            categorize: bool = True,
            **kwargs,
        ) -> None:
            Downloads and deobfuscates the assetbundle to the specified path.
            Also performs media conversion if applicable.
    """

    def __init__(self, info: dict, url_template: str):
        """
        Initializes an assetbundle with the given information.
        Usually called from GkmasManifest.

        Args:
            info (dict): An info dictionary, extracted from protobuf.
            url_template (str): URL template for downloading the assetbundle.
                {o} will be replaced with self.objectName.
        """

        super().__init__(info, url_template)
        self.name += ".unity3d"
        self._idname = f"AB[{self.id:05}] '{self.name}'"
        self._reporter = ProgressReporter(title=self._idname, total=self.size)
        # need to re-instantiate since self._idname has changed

    def __repr__(self) -> str:
        return f"<GkmasAssetBundle {self._idname}>"

    @property
    def canon_repr(self) -> dict:
        canon = super().canon_repr
        canon["name"] = canon["name"].replace(".unity3d", "")
        return canon

    @property
    def _media_class(self) -> type:
        if self.name.startswith("img_"):
            return GkmasUnityImage
        elif self.name.startswith("sud_"):
            return GkmasUnityAudio
        else:
            return GkmasDummyMedia

    def _download_bytes(self) -> dict:
        """
        [INTERNAL] Downloads, and optionally deobfuscates, the assetbundle as raw bytes.
        Sanity checks are implemented in parent class GkmasResource.
        """

        data = super()._download_bytes()
        _bytes, _mtime = data["bytes"], data["mtime"]

        if not _bytes.startswith(UNITY_SIGNATURE):
            self._reporter.update("Deobfuscating")
            _bytes = GkmasAssetBundleDeobfuscator(self.name).process(_bytes)
            if not _bytes.startswith(UNITY_SIGNATURE):
                self._reporter.warning("Downloaded but LEFT OBFUSCATED")
                # Unexpected things may happen...
                # So unlike _download_bytes(), here we don't raise an error and abort.

        return {
            "bytes": _bytes,
            "mtime": _mtime,
        }
