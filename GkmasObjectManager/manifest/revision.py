"""
revision.py
Version control for GkmasManifest.
"""


class GkmasManifestRevision:
    """
    A GKMAS manifest revision, useful for version control at creating/applying diffs.

    Attributes:
        this (int): The revision number of this manifest,
            as represented in the ProtoDB.
        base (int): The revision number of the base manifest,
            *inferred* at API call in fetch() and unused in load().
            base = 0 indicates a complete manifest of 'this' revision
            (which is not necessarily the case if manifest is loaded from a file),
            while base > 0 indicates a diff to be applied to the base manifest.
    """

    def __init__(self, this: int, base: int = 0):
        assert this > 0, "'this' revision number must be positive."
        assert base >= 0, "'base' revision number must be non-negative."
        assert this > base, "'this' revision must be newer than 'base'."
        self.this = this
        self.base = base

    def __repr__(self):
        return f"<GkmasManifestRevision {self}>"

    def __str__(self):
        if self.base == 0:
            return f"v{self.this}"
        else:
            return f"v{self.this}-diff-v{self.base}"

    def _get_canon_repr(self):
        """
        [INTERNAL] Returns the "canonical" representation of the revision,
        either as an integer or a tuple. Used in manifest export.
        """
        if self.base == 0:
            return self.this
        else:
            return (self.this, self.base)

    def __eq__(self, other):
        return self.this == other.this and self.base == other.base

    def __ne__(self, other):
        return not self.__eq__(other)

    # No comparison magic methods; things are starting to get ambiguous at this point.
    # We are primarily concerned with the *difference* between revisions.

    def __sub__(self, other):
        """
        Returns the difference between two revisions.
        Cases where base = 0 is regarded as the "empty base" and processed at instantiation.

                               | self.base < other.base | self.base = other.base | self.base > other.base
        -----------------------+------------------------|------------------------|------------------------
        self.this < other.this |        INVALID         |        INVALID         |        INVALID
        self.this = other.this | other.base - self.base |        INVALID         |        INVALID
        self.this > other.this |        INVALID         | self.this - other.this |        INVALID
        """

        assert (
            self.this == other.this or self.base == other.base
        ), "Comparable revisions must have either the same 'this' or 'base'."
        assert (
            self.this != other.this or self.base != other.base
        ), "Revisions are identical."  # or should we return None?

        if self.this == other.this:
            assert (
                self.base < other.base
            ), "'Base' revision of subtrahend (other) must be newer."
            return GkmasManifestRevision(other.base, self.base)
        else:
            assert (
                self.this > other.this
            ), "'This' revision of minuend (self) must be newer."
            return GkmasManifestRevision(self.this, other.this)

    def __add__(self, other):
        """
        Returns the sum of two revisions.
        Requires self.this == other.base to be valid.
        """

        assert (
            self.this != other.this
        ), "Cannot add revisions with identical 'this' revision."
        a, b = (self, other) if self.this < other.this else (other, self)
        assert a.this == b.base, "Revisions not comparable."
        return GkmasManifestRevision(b.this, a.base)
