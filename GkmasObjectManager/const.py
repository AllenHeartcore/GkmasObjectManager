"""
const.py
Module-wide constants (macro equivalents).
"""

from pathlib import Path
from urllib.parse import urljoin

from .utils import md5sum, sha256sum

# argument type hints
PathArgtype = str | Path

# manifest request
GKMAS_APPID = 400
GKMAS_VERSION = 205000
GKMAS_VERSION_PC = 705000
GKMAS_API_SERVER = "https://api.asset.game-gakuen-idolmaster.jp/"
GKMAS_API_URL = urljoin(
    GKMAS_API_SERVER, f"v2/pub/a/{GKMAS_APPID}/v/{GKMAS_VERSION}/list/"
)
GKMAS_API_URL_PC = urljoin(
    GKMAS_API_SERVER, f"v2/pub/a/{GKMAS_APPID}/v/{GKMAS_VERSION_PC}/list/"
)
GKMAS_API_KEY = "0jv0wsohnnsigttbfigushbtl3a8m7l5"
GKMAS_API_HEADER = {
    "Accept": f"application/x-protobuf,x-octo-app/{GKMAS_APPID}",
    "X-OCTO-KEY": GKMAS_API_KEY,
}

# manifest decrypt
GKMAS_ONLINEPDB_KEY = sha256sum("eSquJySjayO5OLLVgdTd".encode("utf-8"))
GKMAS_ONLINEPDB_KEY_PC = sha256sum("x5HFaJCJywDyuButLM0f".encode("utf-8"))
GKMAS_OCTOCACHE_KEY = md5sum("1nuv9td1bw1udefk".encode("utf-8"))
GKMAS_OCTOCACHE_IV = md5sum("LvAUtf+tnz".encode("utf-8"))

# manifest history
REPO_OBJECT_URL_TEMPLATE = "https://raw.githubusercontent.com/AllenHeartcore/GkmasObjectManager/{branch}/{path}"
MANIFEST_UPDATE_BRANCH = "manifest-update"
WAYBACK_COMMITS_LOG_LOCAL = "wayback_commits.json"
WAYBACK_COMMITS_LOG_REMOTE = REPO_OBJECT_URL_TEMPLATE.format(
    branch=MANIFEST_UPDATE_BRANCH, path=WAYBACK_COMMITS_LOG_LOCAL
)
WAYBACK_OBJECTS_LOG_LOCAL = "wayback_objects.json"
WAYBACK_OBJECTS_LOG_REMOTE = REPO_OBJECT_URL_TEMPLATE.format(
    branch=MANIFEST_UPDATE_BRANCH, path=WAYBACK_OBJECTS_LOG_LOCAL
)
WAYBACK_MANIFEST_URL_TEMPLATE = REPO_OBJECT_URL_TEMPLATE.format(
    branch="{hash}", path="manifests/v{revision:04d}.json"
)

# manifest export
CSV_COLUMNS = ["objectName", "md5", "name", "size", "state"]

# manifest download dispatcher
DEFAULT_DOWNLOAD_PATH = "objects/"

# object download
CHARACTER_ABBREVS = [
    "hski",  # Hanami SaKI
    "ttmr",  # Tsukimura TeMaRi
    "fktn",  # Fujita KoToNe
    "amao",  # Arimura MAO
    "kllj",  # Katsuragi LiLJa
    "kcna",  # Kuramoto ChiNA
    "ssmk",  # Shiun SuMiKa
    "shro",  # Shinosawa HiRO
    "hrnm",  # Himesaki RiNaMi
    "hume",  # Hanami UME
    "hmsz",  # Hataya MiSuZu
    "jsna",  # Juo SeNA
    "atbm",  # Amaya TsuBaMe
    "nasr",  # Neo ASaRi
    "jkno",  # Juo KuNiO
    "trvo",  # VOcal TRainer
    "trda",  # DAnce TRainer
    "trvi",  # VIsual TRainer
    "krnh",  # Kayo RiNHa
    "andk",  # Aoi NaDeshiKo
    "sson",  # Shirakusa ShiON
    "sgka",  # Shirakusa GekKA
    "ktko",  # Kuroi TaKaO
    "cmmn",  # (CoMMoN)
]

# object deobfuscate
GKMAS_UNITY_VERSION = "2022.3.21f1"
UNITY_SIGNATURE = b"UnityFS"

# adventure captioning
DEFAULT_USERNAME = "プロデューサー"
