"""
versioning.py
Version control for GkmasManifest.
"""

# Terminology: Version = (Era, Revision) pair

from ..const import GKMAS_VERSION, GKMAS_VERSION_PC


class EraRevPair:
    """
    A pair of Era-Revision values, used in version control.

    Attributes:
        era (int): The Era value. Documents API changes.
            The protobuf field `uploadVersionId` also takes this value.
            Thought about taking the word "generation" from the protobuf field,
                but in IDOLY PRIDE this field becomes a 16-digit timestamp.
        rev (int): The Revision value, as represented in the ProtoDB.
    """

    era: int
    rev: int

    def __init__(self, era: int, rev: int):
        assert era > 0 or rev == 0, "Era must be positive."
        assert rev >= 0, "Revision must be non-negative."
        self.era = era if rev > 0 else 0  # empty case (0, 0) should be the smallest
        self.rev = rev

    def __repr__(self) -> str:
        return f"<EraRevPair {self}>"

    def __str__(self) -> str:
        return f"{self.era}:{self.rev:04d}"

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
    A GKMAS manifest version, useful for creating/applying diffs.

    Attributes:
        this (EraRevPair): The version of this manifest,
            as represented in the ProtoDB.
        base (EraRevPair): The version of the base manifest,
            *inferred* at API call in fetch() and unused in load().
            base = 0 indicates a complete manifest of 'this' version
            (which is not necessarily the case if manifest is loaded from a file),
            while base > 0 indicates a diff to be applied to the base manifest.
        pc (bool): Whether we're initializing a PC manifest version.
            Defaults to False (mobile).
    """

    this: EraRevPair
    base: EraRevPair

    @staticmethod
    def str2erp(s: str) -> EraRevPair:
        """
        Converts a string representation of an Era-Revision pair to an EraRevPair object.
        """
        era, rev = map(int, s.split(":"))
        return EraRevPair(era, rev)

    def __init__(
        self,
        this: int | str | EraRevPair,
        base: int | str | EraRevPair = 0,
        pc: bool = False,
    ):
        # __sub__ or __add__ calls this constructor with EraRevPair objects
        # also GMV's constructor is intentionally tolerant, while ERP's is strict
        # Valid forms:
        #   - GMV(454)
        #   - GMV(257, pc=True)
        #   - GMV("205100:0033")
        #   - GMV("705100:0030-diff-705100:0027")
        #   - GMV(EraRevPair(705100, 24), EraRevPair(705100, 21))

        if isinstance(this, str):
            if "-diff-" in this:
                assert base == 0, "Base is already specified in 'this' string."
                this, base = this.split("-diff-")
            else:
                base = "0:0"  # circumventing our own same-type assertion... bruh

        if not type(this) == type(base):
            raise TypeError("'this' and 'base' must be of the same type.")

        if isinstance(this, int):
            era = GKMAS_VERSION_PC if pc else GKMAS_VERSION
            this, base = map(lambda rev: EraRevPair(era, rev), (this, base))
            # base = 0 is inherently handled
        elif isinstance(this, str):
            this, base = map(self.str2erp, (this, base))
        elif isinstance(this, EraRevPair):
            pass  # already in the correct form
        else:
            raise TypeError("Unsupported type for GMV constructor.")

        assert this.rev > 0, "'this' revision number must be positive."
        assert base.rev >= 0, "'base' revision number must be non-negative."
        assert this > base, "'this' revision must be newer than 'base'."
        self.this, self.base = this, base
        # 'era' is never overridden except when fetching old manifests,
        # which case should be handled in manifest/__init__.py

    def __repr__(self) -> str:
        return f"<GkmasManifestVersion {self}>"

    def __str__(self) -> str:
        if self.base.rev == 0:
            return f"{self.this}"
        else:
            return f"{self.this}-diff-{self.base}"

    @property
    def canon_repr(self) -> int | tuple[int, int]:
        """
        [INTERNAL] Returns the "canonical" representation of the version,
        either as an integer or a tuple. Used in manifest export.
        """
        if self.base.rev == 0:
            return self.this.rev
        else:
            return (self.this.rev, self.base.rev)

    def __eq__(self, other: "GkmasManifestVersion") -> bool:
        return self.this == other.this and self.base == other.base

    def __ne__(self, other: "GkmasManifestVersion") -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: "GkmasManifestVersion") -> bool:
        return self.this < other.this or (
            self.this == other.this and self.base < other.base
        )

    def __gt__(self, other: "GkmasManifestVersion") -> bool:
        return self.this > other.this or (
            self.this == other.this and self.base > other.base
        )

    def __sub__(self, other: "GkmasManifestVersion") -> "GkmasManifestVersion":
        """
        Returns the difference between two versions.
        Cases where base = 0 is regarded as the "empty base" and processed at instantiation.

        Valid cases:
            - (self.this = other.this) and (self.base < other.base) => returns (other.base - self.base)
            - (self.this > other.this) and (self.base = other.base) => returns (self.this - other.this)
        """

        assert (
            self.this == other.this or self.base == other.base
        ), "Comparable versions must have either the same 'this' or 'base'."
        assert (
            self.this != other.this or self.base != other.base
        ), "Versions are identical."  # or should we return None?

        if self.this == other.this:
            assert (
                self.base < other.base
            ), "'Base' version of subtrahend (other) must be newer."
            return GkmasManifestVersion(other.base, self.base)
        else:
            assert (
                self.this > other.this
            ), "'This' version of minuend (self) must be newer."
            return GkmasManifestVersion(self.this, other.this)

    def __add__(self, other: "GkmasManifestVersion") -> "GkmasManifestVersion":
        """
        Returns the sum of two versions.
        Requires self.this == other.base to be valid.
        """

        assert (
            self.this != other.this
        ), "Cannot add versions with identical 'this' version."
        a, b = (self, other) if self.this < other.this else (other, self)
        assert a.this == b.base, "Versions not comparable."
        return GkmasManifestVersion(b.this, a.base)
