"""
crypt.py
[INTERNAL] GkmasManifest decryptor.
"""

from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CBC
from cryptography.hazmat.primitives.padding import PKCS7


class AESCBCDecryptor:
    """
    General-purpose AES decryptor (CBC mode).

    Attributes:
        cipher (cryptography.hazmat.primitives.ciphers.Cipher): AES cipher object.
        unpadder (cryptography.hazmat.primitives.padding.PKCS7): PKCS7 unpadder object.
        block_size (int): AES block size, fixed at 128 // 8 = 16 bytes.

    Methods:
        process(enc: bytes) -> bytes:
            Decrypts the given ciphertext into plaintext.
    """

    def __init__(self, key: bytes, iv: bytes):
        """
        Initializes the decryptor with the given key and IV.

        Args:
            key (bytes): The AES key.
            iv (bytes): The AES initialization vector.
        """

        self.cipher = Cipher(AES(key), CBC(iv)).decryptor()
        self.unpadder = PKCS7(AES.block_size).unpadder()
        self.block_size = AES.block_size // 8

    def process(self, enc: bytes) -> bytes:
        """
        Decrypts the given ciphertext into plaintext.

        Args:
            enc (bytes): The encrypted bytes to decrypt.
                For some reason there's a single extra 0x01 byte preceding ciphertext
                downloaded from the server, so the method also ensures that
                ciphertext is 16-byte aligned by trimming these leading bytes.
        """

        clen = len(enc) // self.block_size * self.block_size
        enc = enc[-clen:]

        dec = self.cipher.update(enc) + self.cipher.finalize()
        dec = self.unpadder.update(dec) + self.unpadder.finalize()

        return dec
