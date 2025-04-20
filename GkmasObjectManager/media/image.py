"""
media/image.py
Unity image conversion plugin for GkmasAssetBundle,
and PNG image handler for GkmasResource.
"""

from ..log import Logger
from ..const import IMAGE_RESIZE_ARGTYPE
from .dummy import GkmasDummyMedia

from io import BytesIO
from pathlib import Path
from typing import Union, Tuple

import UnityPy
from PIL import Image


logger = Logger()


class GkmasImage(GkmasDummyMedia):
    """Handler for images of common formats recognized by PIL."""

    def __init__(self, name: str, raw: bytes, mtime: str = ""):
        super().__init__(name, raw, mtime)
        self.mimetype = "image"
        self.raw_format = name.split(".")[-1][:-1]

    def _convert(self, raw: bytes, **kwargs) -> bytes:
        return self._img2bytes(Image.open(BytesIO(raw)), **kwargs)

    # don't put 'image_resize' in signature to match the parent class
    def _img2bytes(self, img: Image, **kwargs) -> bytes:
        """
        Args:
            image_resize (Union[None, str, Tuple[int, int]]) = None: Image resizing argument.
                If None, image is downloaded as is.
                If str, string must contain exactly one ':' and image is resized to the specified ratio.
                If Tuple[int, int], image is resized to the specified exact dimensions.
        """

        image_resize = kwargs.get("image_resize", None)
        if image_resize:
            if type(image_resize) == str:
                image_resize = self._determine_new_size(img.size, ratio=image_resize)
            img = img.resize(image_resize, Image.LANCZOS)

        io = BytesIO()
        try:
            img.save(io, format=self.converted_format.upper(), quality=100)
        except OSError:  # cannot write mode RGBA as {self.converted_format}
            img.convert("RGB").save(
                io, format=self.converted_format.upper(), quality=100
            )

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

    def __init__(self, name: str, raw: bytes, mtime: str = ""):
        super().__init__(name, raw, mtime)
        self.raw_format = None  # don't override
        self.converted_format = "png"

    def _convert(self, raw: bytes, **kwargs) -> bytes:
        env = UnityPy.load(raw)
        values = list(env.container.values())
        assert len(values) == 1, f"{self.name} contains {len(values)} images."
        return super()._img2bytes(values[0].read().image, **kwargs)
