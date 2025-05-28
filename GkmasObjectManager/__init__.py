"""
GkmasObjectManager
An object-oriented interface for interacting with object databases ("manifests")
in the mobile game Gakuen Idolm@ster (https://gakuen.idolmaster-official.jp/)
"""

from .manifest import GkmasManifest, fetch, load
from .object import GkmasAssetBundle, GkmasResource
