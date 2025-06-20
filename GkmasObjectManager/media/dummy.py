"""
media/dummy.py
Dummy media conversion plugin.
Serves as a base class & template for other media plugins,
as well as a fallback for unknown media types.
"""

import os
from pathlib import Path
from typing import Callable, Optional, Tuple, Union
from zipfile import ZipFile

from ..rich import ProgressReporter


class GkmasDummyMedia:
    """
    Unrecognized media handler, also the fallback for conversion plugins.

    Attributes:
        ext (str): File extension of the media file.
        downloader (Callable): Function to lazily download raw bytes.
        reporter (ProgressReporter): Reporter for download progress.
        mtime (float): Last modified time of the media file as a timestamp.
        mimetype (str): Media type (e.g., "image", "audio", "video").
        raw (bytes): Raw binary data of the media file.
        raw_format (str): Format of the raw media data.
        converted (bytes): Converted binary data of the media file, if applicable.
        converted_format (str): Format of the converted media data.
        default_converted_format (str): Default format for conversion, if applicable.

    Methods:
        get_data(**kwargs) -> dict:
            Requests data of the desired format.
        export(path: Path, **kwargs):
            Exports the media to the specified path.
    """

    ENABLE_CACHE: bool = True

    ext: str
    mtime: float = 0.0
    downloader: Callable[[], dict]
    reporter: ProgressReporter

    _raw: Optional[bytes] = None
    _converted: Optional[bytes] = None

    # Children should override raw_format if raw bytes is "ready"
    #   or converted_format as the default target, but **not both.**
    # On the other hand, self.mimetype since it's mandatory.
    mimetype: str = ""
    raw_format: str = ""
    converted_format: str = ""
    default_converted_format: str = ""

    # This can't be integrated into Image since it's not about efficiency
    #   where we can return early if image_resize hits cache in _convert(),
    #   but about *correctness* where the same format with a different
    #   image_resize wouldn't even trigger _convert() otherwise.
    # This used to be a global const, but was soon deprecated
    #   since we use kwargs.get() and can't enforce type hint.
    # On the other hand, we can't record the sanitized "new size" tuple here,
    #   since it's about checking cache against user input *before* conversion,
    #   and we don't want to move _determine_new_size() to this class.
    image_resize: Optional[Union[str, Tuple[int, int]]] = None

    def __init__(
        self,
        ext: str,
        downloader: Callable[[], dict],
        reporter: ProgressReporter,
    ):
        self.ext = ext.lower()
        self.downloader = downloader  # lazy downloader
        self.reporter = reporter
        self._init_mimetype()

    def _init_mimetype(self):
        self.mimetype = ""  # TO BE OVERRIDDEN (e.g., "image", "audio", "video")
        self.raw_format = ""  # TO BE OVERRIDDEN, or
        self.default_converted_format = ""  # TO BE OVERRIDDEN (choose one)
        # yeah these two lines appear twice... this time just as a hint

    def _convert(self, raw: bytes) -> bytes:
        raise NotImplementedError  # TO BE OVERRIDDEN

    def get_data(self, **kwargs) -> dict:
        """
        Requests data of the desired format.

        Args:
            {mimetype}_format (str): Desired format for the media type.
            image_resize (Union[str, Tuple[int, int]], optional) = None: Image resizing argument.
                If None, image is downloaded as is.
                If str (must contain exactly one ':'), image is resized to the specified ratio.
                If Tuple[int, int], image is resized to the specified exact dimensions.

        Returns:
            dict: A dictionary of keys "bytes", "mimetype", and "mtime".
        """

        fmt = kwargs.get(
            f"{self.mimetype}_format",
            self.raw_format
            or self.default_converted_format,  # fallback if raw_format is empty
        ).lower()

        if self.raw_format == fmt:  # rawdump
            _bytes = self.raw  # must be called before accessing self.mtime
            return {
                "bytes": _bytes,
                "mimetype": (
                    f"{self.mimetype}/{self.raw_format}"
                    if self.mimetype and self.raw_format
                    else "application/octet-stream"
                ),
                "mtime": self.mtime,
            }

        image_resize = kwargs.get("image_resize", None)
        if (
            self.converted_format != fmt or image_resize != self.image_resize
        ):  # record and convert
            self.converted_format = fmt
            self._converted = None  # invalidate cache
            self.image_resize = image_resize

        _bytes = self.converted
        return {
            "bytes": _bytes,
            "mimetype": (
                "application/zip"
                if _bytes.startswith(b"PK\x03\x04")
                # a bit of a hack, but we don't want to override bookkeeping vars
                else (
                    f"{self.mimetype}/{self.converted_format}"
                    if self.mimetype and self.converted_format
                    else "application/octet-stream"
                    # in case some malicious user escaped the 'if self.raw_format == fmt' branch
                    # by explicitly specifying '_format' as some random value
                )
            ),
            "mtime": self.mtime,
        }

    def _get_predicted_mimesubtype(self, **kwargs) -> str:
        # This is exclusively used for early return in _export_converted(),
        #   to avoid true mimesubtype's dependency on raw bytes.
        #   (By "unpredictable" I'm referring to .zip; elaborated below.)
        # Basically a stripped get_data() that returns only the latter half of 'mimetype'.

        # Key differences:
        # - collapse 'fmt if fmt else DEFAULT' to 'fmt or DEFAULT'
        # - merge !self.mimetype common fallbacks, escalate it above fmt check
        # - instead of 'octet-stream', fallback to self.ext
        # - .zip is *fundamentally* uncatchable and ignored, since we wouldn't know
        #   a certain .acb is a multi-subsong archive before downloading the raw bytes

        fmt = kwargs.get(
            f"{self.mimetype}_format",
            self.raw_format or self.default_converted_format,
        ).lower()
        return fmt if (fmt and self.mimetype) else self.ext

    @property
    def raw(self) -> bytes:
        if self._raw is not None:
            return self._raw  # read from cache
        data = self.downloader()
        self.mtime = data["mtime"]  # unconditionally cache, as a metadata field
        if self.ENABLE_CACHE:
            self._raw = data["bytes"]
        return data["bytes"]  # cached or not, this is "valid"

    @property
    def converted(self) -> bytes:
        if self._converted is not None:
            return self._converted  # assumes proper invalidation beforehand
        raw = self.raw
        self.reporter.update("Converting")
        converted = self._convert(raw)
        if self.ENABLE_CACHE:
            self._converted = converted
        return converted

    def export(self, path: Path, **kwargs):
        """
        Exports the media to the specified path.

        Args:
            path (Path): The path to export the media to.
            convert_{mimetype} (bool): Whether to enable media conversion.
            {mimetype}_format (str): Desired format for the media type.
        """

        # not overriding self.mimetype indicates unhandled media type
        if self.mimetype and kwargs.get(f"convert_{self.mimetype}", True):
            try:
                self._export_converted(path, **kwargs)
            except Exception as e:
                self.reporter.warning(
                    "Conversion failed, fallback to rawdump; exception to follow"
                )
                self._export_raw(path)
                raise e
        else:
            self._export_raw(path)

    def _export_raw(self, path: Path):

        if path.exists():
            self.reporter.warning("Already exists, aborting")
            return

        self.reporter.start()

        path.write_bytes(self.raw)
        if self.mtime:
            os.utime(path, (self.mtime, self.mtime))

        self.reporter.success("Downloaded and rawdumped")

    def _export_converted(self, path: Path, **kwargs):

        # underscored vars are for early return and log only
        _mimesubtype = self._get_predicted_mimesubtype(**kwargs)
        _path = path.with_suffix(f".{_mimesubtype}")
        if _path.exists():
            self.reporter.warning(f"*.{_mimesubtype} already exists, aborting")
            return

        # additional check for existing .zip; yet the unpacked case is still uncovered
        if self.ext == "acb" and path.with_suffix(".zip").exists():
            self.reporter.warning("*.zip already exists, aborting")
            return

        self.reporter.start()

        data = self.get_data(**kwargs)
        mimesubtype = data["mimetype"].split("/")[1]
        path = path.with_suffix(f".{mimesubtype}")  # true mimesubtype

        path.write_bytes(data["bytes"])
        if self.mtime:
            os.utime(path, (self.mtime, self.mtime))

        # This can't be integrated into Audio since _convert() is bytes-to-bytes
        if mimesubtype == "zip" and kwargs.get("unpack_subsongs", False):
            self.reporter.update("Unpacking")
            with ZipFile(path) as z:
                z.extractall(path.parent)  # surprisingly, doesn't keep mtime's
                for file in z.namelist():
                    os.utime(path.parent / file, (self.mtime, self.mtime))
            path.unlink()
            self.reporter.success(f"Downloaded and unpacked to {path.parent}")
        else:
            self.reporter.success(f"Downloaded and converted to {mimesubtype.upper()}")
