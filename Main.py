from GkmasObjectManager import GkmasManifest
from GkmasObjectManager.const import ALL_ASSETBUNDLES, ALL_RESOURCES


manifest = GkmasManifest("EncryptedCache/octocacheevai_v81")
manifest.export("DecryptedCache/v81")
manifest.download(ALL_ASSETBUNDLES, ALL_RESOURCES)
