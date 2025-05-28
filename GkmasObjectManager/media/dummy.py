"""
media/dummy.py
Dummy media conversion plugin.
Serves as a base class & template for other media plugins,
as well as a fallback for unknown media types.
"""

import os
from pathlib import Path
from typing import Callable
from zipfile import ZipFile

from ..utils import Logger

logger = Logger()


class GkmasDummyMedia:
    """
    Unrecognized media handler, also the fallback for conversion plugins.

    Attributes:
        name (str): Name of the media file (for logging purposes).
        downloader (Callable): Function to lazily download raw bytes.
        mtime (float): Last modified time of the media file as a timestamp.
        mimetype (str): Media type (e.g., "image", "audio", "video").
        raw (bytes): Raw binary data of the media file.
        raw_format (str): Format of the raw media data.
        converted (bytes): Converted binary data of the media file, if applicable.
        converted_format (str): Format of the converted media data.

    Methods:
        get_data(**kwargs) -> dict:
            Requests data of the desired format.
        export(path: Path, **kwargs):
            Exports the media to the specified path.
    """

    ENABLE_CACHE = True

    def __init__(self, name: str, downloader: Callable[[], dict]):
        self.name = name  # only for logging
        self._name_ext = name.split(".")[-1][:-1].lower()
        self.downloader = downloader  # lazy downloader

        self.mtime = None
        self.raw = None  # raw binary data (we don't want to reencode known formats)
        self.converted = None  # converted binary data (if applicable)

        # Children should override raw_format if raw bytes is "ready"
        #   or converted_format as the default target, but **not both.**
        # This mutual exclusivity forces the following fallbacks
        #   to appear here, otherwise we get AttributeError's.
        # This isn't a problem for self.mimetype since it's mandatory.
        self.raw_format = ""
        self.converted_format = ""
        self.default_converted_format = ""
        self._init_mimetype()

        # This can't be integrated into Image since it's not about efficiency
        #   where we can return early if image_resize hits cache in _convert(),
        #   but about *correctness* where the same format with a different
        #   image_resize wouldn't even trigger _convert() otherwise.
        # This is of type Union[None, str, Tuple[int, int]],
        #   which used to be a global const, but was soon deprecated
        #   since we use kwargs.get() and can't enforce type hint.
        # On the other hand, we can't record the sanitized "new size" tuple here,
        #   since it's about checking cache against user input *before* conversion,
        #   and we don't want to move _determine_new_size() to this class.
        self.image_resize = None

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
            image_resize (Union[None, str, Tuple[int, int]]) = None: Image resizing argument.
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
            _bytes = self._get_raw()  # must be called before accessing self.mtime
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
            self.converted = None  # invalidate cache
            self.image_resize = image_resize

        _bytes = self._get_converted()
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
        # - instead of 'octet-stream', fallback to self._name_ext
        # - .zip is *fundamentally* uncatchable and ignored, since we wouldn't know
        #   a certain .acb is a multi-subsong archive before downloading the raw bytes

        fmt = kwargs.get(
            f"{self.mimetype}_format",
            self.raw_format or self.default_converted_format,
        ).lower()
        return fmt if (fmt and self.mimetype) else self._name_ext

    def _get_raw(self) -> bytes:
        if self.raw is not None:
            return self.raw  # read from cache
        data = self.downloader()
        self.mtime = data["mtime"]  # unconditionally cache, as a metadata field
        if self.ENABLE_CACHE:
            self.raw = data["bytes"]
        return data["bytes"]  # cached or not, this is "valid"

    def _get_converted(self) -> bytes:
        if self.converted is not None:
            return self.converted  # assumes proper invalidation beforehand
        converted = self._convert(self._get_raw())
        if self.ENABLE_CACHE:
            self.converted = converted
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
                logger.warning(
                    f"{self.name} failed to convert, fallback to rawdump; exception to follow"
                )
                self._export_raw(path)
                raise e
        else:
            self._export_raw(path)

    def _export_raw(self, path: Path):

        if path.exists():
            logger.warning(f"{self.name} already exists, aborting")
            return

        path.write_bytes(self._get_raw())
        if self.mtime:
            os.utime(path, (self.mtime, self.mtime))
        logger.success(f"{self.name} downloaded")

    def _export_converted(self, path: Path, **kwargs):

        # underscored vars are for early return and log only
        _mimesubtype = self._get_predicted_mimesubtype(**kwargs)
        _path = path.with_suffix(f".{_mimesubtype}")
        if _path.exists():
            # self.name is heavily reused in children, and we don't want to
            # change Media's init interface just for reassembly here
            _name = f"{self.name.split(".")[0]}.{_mimesubtype}'"
            logger.warning(f"{_name} already exists, aborting")
            return

        # additional check for existing .zip; yet the unpacked case is still uncovered
        if self._name_ext == "acb" and path.with_suffix(".zip").exists():
            _name = f"{self.name.split('.')[0]}.zip"
            logger.warning(f"{_name} already exists, aborting")
            return

        data = self.get_data(**kwargs)
        mimesubtype = data["mimetype"].split("/")[1]
        path = path.with_suffix(f".{mimesubtype}")  # true mimesubtype

        path.write_bytes(data["bytes"])
        if self.mtime:
            os.utime(path, (self.mtime, self.mtime))
        logger.success(f"{self.name} downloaded and converted to {mimesubtype.upper()}")

        # This can't be integrated into Audio since _convert() is bytes-to-bytes
        if mimesubtype == "zip" and kwargs.get("unpack_subsongs", False):
            with ZipFile(path) as z:
                z.extractall(path.parent)  # surprisingly, doesn't keep mtime's
                for file in z.namelist():
                    os.utime(path.parent / file, (self.mtime, self.mtime))
            path.unlink()
            logger.success(f"{self.name} unpacked to {path.parent}")
