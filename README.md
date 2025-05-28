# GkmasObjectManager

An OOP interface for interacting with object databases
in the mobile game [Gakuen Idolm@ster](https://gakuen.idolmaster-official.jp/).

Designed with ❤ by [Ziyuan "Heartcore" Chen](https://allenheartcore.github.io/). <br>
Refactored from [gkmasToolkit](https://github.com/kishidanatsumi/gkmasToolkit) by Kishida Natsumi, <br>
which in turn was adapted from [HoshimiToolkit](https://github.com/MalitsPlus/HoshimiToolkit) by Vibbit. <br>
Request API & decryption algorithms borrowed from [HatsuboshiToolkit](https://github.com/DreamGallery/HatsuboshiToolkit) by DreamGallery.



## Features

- Fetch, decrypt, deserialize, and export manifest as ProtoDB, JSON, or CSV
- Differentiate between / add (apply patch to) manifest revisions
- Download and deobfuscate assetbundles and resources in parallel
- Media conversion plugins for Texture2D, AudioClip audio, AWB audio, and USM video



## Example Usage

```python
import GkmasObjectManager as gom

m = gom.fetch()  # fetch latest
m.export("manifest.json")

m_old = gom.load("octocacheevai")
m_diff = m - m_old
m_diff.export("manifest_diff.json")

m.download(
    "img.*cidol.*full.*", "img.*csprt.*full.*",  # character & support cards
    image_format="JPEG", image_resize="16:9"
)
m.download("sud.*inst.*.awb", audio_format="WAV")  # instrumental songs
m.download("mov.*cidol.*loop.usm", video_format="MP4")  # animated character cards
m.download(
    "sud_vo_adv_unit.*",
    path="mainstory_voicelines",
    audio_format="mp3",  # applies to all subsongs
    unpack_subsongs=True,  # unpack ZIP to output directory
)

m.download_preset("presets/namecard_kit.yml")
```



## Class Hierarchy

- `manifest.decrypt.AESCBCDecryptor` - Manifest decryption
- `manifest.octodb_pb2.Database` - ProtoDB deserialization
- `manifest.manifest.GkmasManifest` - **ENTRY POINT**
  - `manifest.revision.GkmasManifestRevision` - Manifest revision management
  - `manifest.listing.GkmasObjectList` - Object listing and indexing
    - `object.resource.GkmasResource` - Non-Unity object
      - `media.dummy.GkmasDummyMedia` - Base class for media conversion plugins
      - `media.image.GkmasImage` - PNG image handling
      - `media.audio.GkmasAudio` - MP3 audio handling
      - `media.audio.GkmasAWBAudio` - ACB/AWB audio conversion
      - `media.video.GkmasUSMVideo` - USM video conversion
    - `object.deobfuscate.GkmasAssetBundleDeobfuscator`
    - `object.assetbundle.GkmasAssetBundle` - Unity object
      - `media.dummy.GkmasDummyMedia`
      - `media.image.GkmasUnityImage` - Texture2D image handling
      - `media.audio.GkmasUnityAudio` - AudioClip audio handling
