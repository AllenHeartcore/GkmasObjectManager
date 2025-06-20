"""
media/video.py
USM video conversion plugin for GkmasResource.
"""

import subprocess

from .dummy import GkmasDummyMedia


class GkmasUSMVideo(GkmasDummyMedia):
    """Conversion plugin for USM videos."""

    def _init_mimetype(self):
        self.mimetype = "video"
        self.default_converted_format = "mp4"

    def _convert(self, raw: bytes) -> bytes:

        return subprocess.run(
            [
                "ffmpeg",
                "-i",
                "pipe:0",  # input bytestream
                "-f",
                self.converted_format,
                "-preset",
                "ultrafast",
                "-movflags",
                "faststart+frag_keyframe",
                # otherwise libx264 reports 'muxer does not support non seekable output'
                "pipe:1",  # output bytestream
            ],
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # disposed
            check=True,
        ).stdout
