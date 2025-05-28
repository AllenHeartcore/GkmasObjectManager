"""
media/video.py
USM video conversion plugin for GkmasResource.
"""

import ffmpeg

from ..utils import Logger
from .dummy import GkmasDummyMedia

logger = Logger()


class GkmasUSMVideo(GkmasDummyMedia):
    """Conversion plugin for USM videos."""

    def _init_mimetype(self):
        self.mimetype = "video"
        self.default_converted_format = "mp4"

    def _convert(self, raw: bytes) -> bytes:

        stream_in = ffmpeg.input("pipe:0")
        stream_out = ffmpeg.output(
            stream_in,
            "pipe:1",
            vcodec="libx264",
            preset="ultrafast",
            format=self.converted_format,
            movflags="frag_keyframe",
            # otherwise libx264 reports 'muxer does not support non seekable output'
        )

        return ffmpeg.run(
            stream_out,
            input=raw,
            capture_stdout=True,
            capture_stderr=True,
        )[0]
