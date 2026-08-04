"""
versioning.py
Version control for GkmasManifest.
"""

# Terminology: Version = (Era, Revision) pair

from ..const import GKMAS_VERSION


class EraRevPair:
    """
    A pair of Era-Revision values, used in version control.

    Attributes:
        era (int): The Era value, or `GKMAS_VERSION` when making API calls.
            Documents API changes (previously 205000, now 705100).
            The protobuf field `uploadVersionId` also takes this value.
            Thought about taking the word "generation" from the protobuf field,
                but in IDOLY PRIDE this field becomes a 16-digit timestamp.
        rev (int): The Revision value, as represented in the ProtoDB.
    """

    era: int
    rev: int

    def __init__(self, rev: int, era: int = GKMAS_VERSION):
        assert rev > 0, "'rev' must be positive."
        assert era > 0, "'era' must be positive."
        self.era = era
        self.rev = rev

    def __repr__(self) -> str:
        return f"<EraRevPair {self}>"

    def __str__(self) -> str:
        return f"v{self.era}:{self.rev}"

    def __eq__(self, other: "EraRevPair") -> bool:
        return self.era == other.era and self.rev == other.rev

    def __ne__(self, other: "EraRevPair") -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: "EraRevPair") -> bool:
        return self.era < other.era or (self.era == other.era and self.rev < other.rev)

    def __gt__(self, other: "EraRevPair") -> bool:
        return self.era > other.era or (self.era == other.era and self.rev > other.rev)


class GkmasManifestVersion:
    """
    A GKMAS manifest version, used in version control at creating/applying diffs.

    Attributes:
        this (int): The revision number of this manifest,
            as represented in the ProtoDB.
        base (int): The revision number of the base manifest,
            *inferred* at API call in fetch() and unused in load().
            base = 0 indicates a complete manifest of 'this' revision
            (which is not necessarily the case if manifest is loaded from a file),
            while base > 0 indicates a diff to be applied to the base manifest.
    """

    this: int
    base: int

    def __init__(self, this: int, base: int = 0):
        assert this > 0, "'this' revision number must be positive."
        assert base >= 0, "'base' revision number must be non-negative."
        assert this > base, "'this' revision must be newer than 'base'."
        self.this = this
        self.base = base

    def __repr__(self) -> str:
        return f"<GkmasManifestVersion {self}>"

    def __str__(self) -> str:
        if self.base == 0:
            return f"v{self.this}"
        else:
            return f"v{self.this}-diff-v{self.base}"

    @property
    def canon_repr(self) -> int | tuple[int, int]:
        """
        [INTERNAL] Returns the "canonical" representation of the revision,
        either as an integer or a tuple. Used in manifest export.
        """
        if self.base == 0:
            return self.this
        else:
            return (self.this, self.base)

    def __eq__(self, other: "GkmasManifestVersion") -> bool:
        return self.this == other.this and self.base == other.base

    def __ne__(self, other: "GkmasManifestVersion") -> bool:
        return not self.__eq__(other)

    # No comparison magic methods; things are starting to get ambiguous at this point.
    # We are primarily concerned with the *difference* between revisions.

    def __sub__(self, other: "GkmasManifestVersion") -> "GkmasManifestVersion":
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
            return GkmasManifestVersion(other.base, self.base)
        else:
            assert (
                self.this > other.this
            ), "'This' revision of minuend (self) must be newer."
            return GkmasManifestVersion(self.this, other.this)

    def __add__(self, other: "GkmasManifestVersion") -> "GkmasManifestVersion":
        """
        Returns the sum of two revisions.
        Requires self.this == other.base to be valid.
        """

        assert (
            self.this != other.this
        ), "Cannot add revisions with identical 'this' revision."
        a, b = (self, other) if self.this < other.this else (other, self)
        assert a.this == b.base, "Revisions not comparable."
        return GkmasManifestVersion(b.this, a.base)
