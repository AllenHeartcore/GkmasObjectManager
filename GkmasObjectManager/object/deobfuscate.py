"""
obfuscate.py
[INTERNAL] GkmasAssetBundle deobfuscator.
"""


class GkmasAssetBundleDeobfuscator:
    """
    Assetbundle deobfuscator for GKMAS.
    Algorithm courtesy of github.com/MalitsPlus.
    ('maskString' is refactored to 'key' and 'maskBytes' to 'mask'.)

    Attributes:
        mask (bytes): Obfuscation mask.
        offset (int): Byte write pointer offset.
        stream_pos (int): Byte read pointer offset.
        header_len (int): Length of the obfuscated header.

    Methods:
        process(enc: bytes) -> bytes:
            Deobfuscates the given obfuscated bytes into plaintext.
    """

    offset: int
    stream_pos: int
    header_len: int
    mask: bytes

    def __init__(
        self,
        key: str,
        offset: int = 0,
        stream_pos: int = 0,
        header_len: int = 256,
    ):
        """
        Initializes a deobfuscator with given key and parameters.

        Args:
            key (str): A string key for making mask.
            offset (int) = 0: Byte write pointer offset.
            stream_pos (int) = 0: Byte read pointer offset.
            header_len (int) = 256: Length of the obfuscated header.
        """

        self.offset = offset
        self.stream_pos = stream_pos
        self.header_len = header_len
        self.mask = self._make_mask(key.replace(".unity3d", ""))

    @staticmethod
    def _make_mask(key: str) -> bytes:
        """
        [INTERNAL] Generates an obfuscation mask from the given key.
        """

        keysize = len(key)
        masksize = keysize * 2
        mask = bytearray(masksize)
        key = bytes(key, "utf-8")

        for i, char in enumerate(key):
            mask[i * 2] = char
            mask[masksize - 1 - i * 2] = ~char & 0xFF  # cast to unsigned

        x = 0x9B
        for b in mask:
            x = (((x & 1) << 7) | (x >> 1)) ^ b

        return bytes([b ^ x for b in mask])

    def process(self, enc: bytes) -> bytes:
        """
        Deobfuscates the given obfuscated bytes into plaintext.

        Args:
            enc (bytes): The obfuscated bytes to deobfuscate.
        """

        buf = bytearray(enc)

        i = 0
        masksize = len(self.mask)
        while self.stream_pos + i < self.header_len:
            buf[self.offset + i] ^= self.mask[
                self.stream_pos + i - int((self.stream_pos + i) / masksize) * masksize
            ]
            i += 1

        return bytes(buf)
