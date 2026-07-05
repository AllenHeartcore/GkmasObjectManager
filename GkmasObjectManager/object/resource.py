"""
resource.py
General-purpose resource downloading.
"""


class GkmasResource:
    """
    A general-purpose binary resource, presumably multimedia instead of an assetbundle.

    Attributes:
        id (int): Resource ID, unique across manifests.
        name (str): Human-readable name, unique across manifests.
        objectName (str): Object name on server, 6-character alphanumeric.
        size (int): Resource size in bytes, used for integrity check.
        md5 (str): MD5 hash of the resource, used for integrity check.
        state (str): Resource state in manifest (ADD/UPDATE), unused for now.
            Other possible states of NONE, LATEST, and DELETE have not yet been observed.

    Methods:
        download(
            path: str | Path = DEFAULT_DOWNLOAD_PATH,
            categorize: bool = True,
            **kwargs,
        ) -> None:
            Downloads the resource to the specified path.
    """

    id: int
    name: str
    objectName: str
    size: int
    md5: str

    _fields: list[str]
    _idname: str
    _url: str
    _deobf_key: str

    def __init__(self, info: dict, url_template: str, _deobf_key: str = ""):
        """
        Initializes a resource with the given information.
        Usually called from GkmasManifest.

        Args:
            info (dict): An info dictionary, extracted from protobuf.
            url_template (str): URL template for downloading the resource.
                {o} will be replaced with self.objectName.
        """
        #   _deobf_key (str): ignored; for class compatibility only

        self._fields = list(info.keys())
        for field in self._fields:
            setattr(self, field, info[field])

        self._idname = f"RS[{self.id:05}] '{self.name}'"
        self._url = url_template.format(o=self.objectName)

    def __repr__(self) -> str:
        return f"<GkmasResource {self._idname}>"

    @property
    def canon_repr(self) -> dict:
        # this format retains the order of fields
        return {field: getattr(self, field) for field in self._fields}
