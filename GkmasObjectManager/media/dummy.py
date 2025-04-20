"""
media/dummy.py
Dummy media conversion plugin.
Serves as a base class & template for other media plugins,
as well as a fallback for unknown media types.
"""

from ..log import Logger

import os
import base64
from pathlib import Path
from typing import Tuple

from zipfile import ZipFile
from email.utils import parsedate_to_datetime


logger = Logger()


class GkmasDummyMedia:
    """Unrecognized media handler, also the fallback for conversion plugins."""

    def __init__(self, name: str, raw: bytes, mtime: str = ""):
        self.name = name  # only for logging
        self.mtime = parsedate_to_datetime(mtime).timestamp() if mtime else None
        self.raw = raw  # raw binary data (we don't want to reencode known formats)
        self.converted = None  # converted binary data (if applicable)

        self.mimetype = None  # TO BE OVERRIDDEN (e.g., "image", "audio", "video")
        self.raw_format = None  # TO BE OVERRIDDEN
        self.converted_format = None  # TO BE OVERRIDDEN

    def _convert(self, raw: bytes, **kwargs) -> bytes:
        raise NotImplementedError  # TO BE OVERRIDDEN

    def get_data(self, **kwargs) -> Tuple[bytes, str]:

        fmt = kwargs.get(
            f"{self.mimetype}_format",
            self.raw_format or self.converted_format,  # fallback if raw_format is None
        )

        if self.raw_format == fmt:  # rawdump
            return self.raw, (
                f"{self.mimetype}/{self.raw_format}"
                if self.mimetype and self.raw_format
                else "application/octet-stream"
            )

        if self.converted_format != fmt:  # record and convert
            self.converted_format = fmt
            self.converted = None

        if self.converted is None:
            self.converted = self._convert(self.raw, **kwargs)
            # the only place where **kwargs are used is image_resize in GkmasImage

        return self.converted, (
            "application/zip"
            if self.converted.startswith(b"PK\x03\x04")
            # a bit of a hack, but we don't want to override bookkeeping vars
            else (
                f"{self.mimetype}/{self.converted_format}"
                if self.mimetype and self.converted_format
                else "application/octet-stream"
                # in case some malicious user escaped the 'if self.raw_format == fmt' branch
                # by explicitly specifying 'None_format' as some random value
            )
        )

    def get_embed_url(self, **kwargs) -> str:
        data, mimetype = self.get_data(**kwargs)
        return f"data:{mimetype};base64,{base64.b64encode(data).decode()}"

    def export(self, path: Path, **kwargs):
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
        path.write_bytes(self.raw)
        if self.mtime:
            os.utime(path, (self.mtime, self.mtime))
        logger.success(f"{self.name} downloaded")

    def _export_converted(self, path: Path, **kwargs):
        data, mimetype = self.get_data(**kwargs)
        mimesubtype = mimetype.split("/")[1]
        path.with_suffix(f".{mimesubtype}").write_bytes(data)
        if self.mtime:
            os.utime(path.with_suffix(f".{mimesubtype}"), (self.mtime, self.mtime))
        logger.success(f"{self.name} downloaded and converted to {mimesubtype.upper()}")

        if mimesubtype == "zip" and kwargs.get("unpack_subsongs", False):
            with ZipFile(path.with_suffix(f".{mimesubtype}")) as z:
                z.extractall(path.parent)  # surprisingly, doesn't keep mtime's
                for file in z.namelist():
                    os.utime(path.parent / file, (self.mtime, self.mtime))
            path.with_suffix(f".{mimesubtype}").unlink()
            logger.success(f"{self.name} unpacked to {path.parent}")
