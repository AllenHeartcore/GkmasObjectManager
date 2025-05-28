"""
media/image.py
Unity image conversion plugin for GkmasAssetBundle,
and PNG image handler for GkmasResource.
"""

from io import BytesIO
from typing import Tuple, Union

import UnityPy
from PIL import Image

from ..utils import Logger
from .dummy import GkmasDummyMedia

logger = Logger()


class GkmasImage(GkmasDummyMedia):
    """Handler for images of common formats recognized by PIL."""

    def _init_mimetype(self):
        self.mimetype = "image"
        self.raw_format = self._name_ext

    def _convert(self, raw: bytes) -> bytes:
        return self._img2bytes(Image.open(BytesIO(raw)))

    def _img2bytes(self, img: Image) -> bytes:

        image_resize = self.image_resize
        if image_resize:
            if isinstance(image_resize, str):
                image_resize = self._determine_new_size(img.size, ratio=image_resize)
            img = img.resize(image_resize, Image.LANCZOS)

        if img.mode == "RGBA":
            if img.getchannel("A").getextrema() == (255, 255):  # fully opaque
                img = img.convert("RGB")

        io = BytesIO()
        try:
            img.save(io, format=self.converted_format, quality=100)
        except OSError:  # cannot write mode RGBA as {self.converted_format}
            logger.warning(
                f"{self.converted_format} doesn't support RGBA mode, fallback to PNG."
            )
            self.converted_format = "png"
            img.save(io, format="PNG", quality=100)

        return io.getvalue()

    def _determine_new_size(
        self,
        size: Tuple[int, int],
        ratio: str,
        mode: Union["maximize", "ensure_fit", "preserve_npixel"] = "maximize",
    ) -> Tuple[int, int]:
        """
        [INTERNAL] Determines the new size of an image based on a given ratio.

        mode can be one of (terms borrowed from PowerPoint):
        - 'maximize': Enlarges the image to fit the ratio.
        - 'ensure_fit': Shrinks the image to fit the ratio.
        - 'preserve_npixel': Maintains approximately the same pixel count.

        Example: Given ratio = '4:3', an image of size (1920, 1080) is resized to:
        - (1920, 1440) in 'maximize' mode,
        - (1440, 1080) in 'ensure_fit' mode, and
        - (1663, 1247) in 'preserve_npixel' mode.
        """

        ratio = ratio.split(":")
        if len(ratio) != 2:
            raise ValueError("Invalid ratio format. Use 'width:height'.")

        ratio = (float(ratio[0]), float(ratio[1]))
        if ratio[0] <= 0 or ratio[1] <= 0:
            raise ValueError("Invalid ratio values. Must be positive.")

        ratio = ratio[0] / ratio[1]
        w, h = size
        ratio_old = w / h
        if ratio_old == ratio:
            return size

        w_new, h_new = w, h
        if mode == "preserve_npixel":
            pixel_count = w * h
            h_new = (pixel_count / ratio) ** 0.5
            w_new = h_new * ratio
        elif (mode == "maximize" and ratio_old > ratio) or (
            mode == "ensure_fit" and ratio_old < ratio
        ):
            h_new = w / ratio
        else:
            w_new = h * ratio

        round = lambda x: int(x + 0.5)  # round to the nearest integer
        return round(w_new), round(h_new)


class GkmasUnityImage(GkmasImage):
    """Conversion plugin for Unity images."""

    def _init_mimetype(self):
        self.mimetype = "image"
        self.default_converted_format = "png"

    def _convert(self, raw: bytes) -> bytes:
        env = UnityPy.load(raw)
        values = list(env.container.values())
        assert len(values) == 1, f"{self.name} contains {len(values)} images."
        return super()._img2bytes(values[0].read().image)
