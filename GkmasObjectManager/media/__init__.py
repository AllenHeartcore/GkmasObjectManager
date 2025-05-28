"""
media/
Multimedia (images, audio, video, etc.) management.
Instantiated by GkmasResource or descendants.
"""

import UnityPy

from ..const import GKMAS_UNITY_VERSION
from .dummy import GkmasDummyMedia

UnityPy.config.FALLBACK_UNITY_VERSION = GKMAS_UNITY_VERSION
