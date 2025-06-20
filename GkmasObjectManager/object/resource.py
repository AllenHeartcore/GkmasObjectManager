"""
resource.py
General-purpose resource downloading.
"""

import re
from email.utils import parsedate_to_datetime
from pathlib import Path
from queue import Queue
from typing import Optional

import requests
from rich.progress import Progress

from ..adv import GkmasAdventure
from ..const import CHARACTER_ABBREVS, DEFAULT_DOWNLOAD_PATH, PathArgtype
from ..media import GkmasDummyMedia
from ..media.audio import GkmasACBAudio, GkmasAudio, GkmasAWBAudio
from ..media.image import GkmasImage
from ..media.video import GkmasUSMVideo
from ..rich import ProgressReporter
from ..utils import md5sum


class GkmasResource:
    """
    A general-purpose binary resource, presumably multimedia instead of an assetbundle.

    Attributes:
        id (int): Resource ID, unique across manifests.
        name (str): Human-readable name, unique across manifests.
        objectName (str): Object name on server, 6-character alphanumeric.
        size (int): Resource size in bytes, used for integrity check.
        md5 (str): MD5 hash of the resource, used for integrity check.
        state (str): Resource state in manifest (ADD/UPDATE), unused for now.
            Other possible states of NONE, LATEST, and DELETE have not yet been observed.

    Methods:
        download(
            path: Union[str, Path] = DEFAULT_DOWNLOAD_PATH,
            categorize: bool = True,
            **kwargs,
        ) -> None:
            Downloads the resource to the specified path.
    """

    id: int
    name: str
    objectName: str
    size: int
    md5: str

    _fields: list[str]
    _idname: str
    _url: str
    _media: Optional[GkmasDummyMedia] = None
    _reporter: ProgressReporter

    def __init__(self, info: dict, url_template: str):
        """
        Initializes a resource with the given information.
        Usually called from GkmasManifest.

        Args:
            info (dict): An info dictionary, extracted from protobuf.
            url_template (str): URL template for downloading the resource.
                {o} will be replaced with self.objectName.
        """

        self._fields = list(info.keys())
        for field in self._fields:
            setattr(self, field, info[field])

        self._idname = f"RS[{self.id:05}] '{self.name}'"
        self._url = url_template.format(o=self.objectName)

        # placeholder for download progress reporter
        self._reporter = ProgressReporter(title=self._idname, total=self.size)

    def __repr__(self) -> str:
        return f"<GkmasResource {self._idname}>"

    @property
    def canon_repr(self) -> dict:
        # this format retains the order of fields
        return {field: getattr(self, field) for field in self._fields}

    @property
    def _media_class(self) -> type:
        if self.name.startswith("img_"):
            return GkmasImage
        elif self.name.startswith("sud_") and self.name.endswith(".awb"):
            return GkmasAWBAudio
        elif self.name.startswith("sud_") and self.name.endswith(".acb"):
            return GkmasACBAudio
        elif self.name.startswith("sud_"):
            return GkmasAudio
        elif self.name.startswith("mov_"):
            return GkmasUSMVideo
        elif self.name.startswith("adv_"):
            return GkmasAdventure
        else:
            return GkmasDummyMedia

    @property
    def media(self) -> GkmasDummyMedia:
        """
        [INTERNAL] Instantiates a high-level media class based on the resource name.
        Used to dispatch download and extraction.
        SIDE EFFECT: Also registers progress reporter.
        """

        if self._media is None:
            self._media = self._media_class(
                self.name.split(".")[-1],  # use extension as raw format
                self._download_bytes,
                self._reporter,
            )

        return self._media

    def get_data(self, **kwargs) -> dict:
        """
        Requests object data, potentially converting it to a specific format.
        For **kwargs usage, see get_data() methods of GkmasDummyMedia and descendants in media/.

        Args:
            convert_{mimetype} (bool): Whether to enable media conversion.
            {mimetype}_format (str): Desired format for the media type.

        Returns:
            dict: A dictionary of keys "bytes", "mimetype", and "mtime".
        """
        self._reporter.register(**kwargs)
        return self.media.get_data(**kwargs)

    def download(
        self,
        path: PathArgtype = DEFAULT_DOWNLOAD_PATH,
        categorize: bool = True,
        **kwargs,
    ):
        """
        Downloads the resource to the specified path.

        Args:
            path (Union[str, Path]) = DEFAULT_DOWNLOAD_PATH: A directory or a file path.
                If a directory, subdirectories are auto-determined based on the resource name.
            categorize (bool) = True: Whether to put the downloaded object into subdirectories.
                If False, the object is directly downloaded to the specified 'path'.
        """

        self._reporter.register(**kwargs)
        path = self._download_path(path, categorize)
        self.media.export(path, **kwargs)

    def _download_path(self, path: PathArgtype, categorize: bool) -> Path:
        """
        [INTERNAL] Refines the download path based on user input.
        Appends subdirectories unless a definite file path (with suffix) is given.
        Delimiter is hardcoded as '_'.

        path is not necessarily of type Path,
        since we don't expect the client to import pathlib in advance.

        Example:
            path = 'out/' and self.name = 'type_subtype-detail.ext'
            will be refined to 'out/type/subtype/type_subtype-detail.ext'
            if categorize is True, and 'out/type_subtype-detail.ext' otherwise.
        """

        path = Path(path)

        if path.suffix == "":  # is directory
            if categorize:
                path = path / self._determine_subdir(self.name) / self.name
            else:
                path = path / self.name

        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _determine_subdir(filename: str) -> Path:
        """
        [INTERNAL] Automatically organize files into nested subdirectories,
        stopping at the first 'character identifier'.
        """

        filename = Path(filename).stem  # remove extension

        # Ignore everything after the first number after '-' or '_'
        filename = re.split(r"[-_]\d", filename)[0]

        for char in CHARACTER_ABBREVS:
            if char in filename:
                # Ignore everything after 'char', and trim trailing '-' or '_'
                filename = filename.split(char)[0] + char
                break

        return Path(*filename.split("_"))

    def _download_bytes(self) -> dict:
        """
        [INTERNAL] Downloads the resource from the server and performs sanity checks
        on HTTP status code, size, and MD5 hash. Returns the resource as raw bytes.
        """

        with requests.get(self._url, timeout=10, stream=True) as response:
            response.raise_for_status()

            chunks = []
            mtime = response.headers.get("Last-Modified", "")

            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                chunks.append(chunk)
                self._reporter.update("Downloading", advance=len(chunk))

            content = b"".join(chunks)

        # We're being strict here by aborting the download process
        # if any of the sanity checks fail, in order to avoid corrupted output.
        # The client can always retry; just ignore the "file already exists" warnings.
        # Note: Returning empty bytes is unnecessary, since _reporter.error() raises an exception.

        _size = len(content)
        if _size != self.size:
            self._reporter.error(f"Invalid size: expected {self.size}, got {_size}")

        _md5 = md5sum(content).hex()
        if _md5 != self.md5:
            self._reporter.error(f"Invalid MD5 hash: expected {self.md5}, got {_md5}")

        return {
            "bytes": content,
            "mtime": parsedate_to_datetime(mtime).timestamp() if mtime else None,
        }
