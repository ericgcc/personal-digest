"""Language resolution and normalization for ReadSight.

ReadSight addresses languages by hyphenation-pattern code (``en-us``, ``es``,
``fr``, ``de-1996``), while the Digest System stores a human-readable label in
digest frontmatter (``language: English``). This module is the single place
where the two vocabularies meet.

Resolution rules, in priority order (never silently fall back to English):

1. explicit run/digest metadata — the digest frontmatter ``language`` value;
2. existing project language configuration — the registry, when it declares one;
3. an existing language-detection utility — the repository has none, so this
   step is left as an extension point;
4. otherwise the language is *unknown* and the readability limitation is
   recorded explicitly.

The mapping is intentionally isolated here and is extensible by adding entries
to :data:`LANGUAGE_ALIASES`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Mapping, Sequence

import readsight as rs

UNKNOWN_LANGUAGE = "unknown"

#: Normalized language label or code -> ReadSight hyphenation code.
#:
#: Keys are lowercased, with ``_`` replaced by ``-``. Names, ISO 639-1 codes and
#: ISO 639-2/T..B codes all resolve here so digest frontmatter such as
#: ``language: English``, ``language: en`` or ``language: spa`` all work.
LANGUAGE_ALIASES: dict[str, str] = {
    # English
    "en": "en-us",
    "eng": "en-us",
    "english": "en-us",
    "en-us": "en-us",
    "en-gb": "en-gb",
    "en-uk": "en-gb",
    "british-english": "en-gb",
    "american-english": "en-us",
    # Spanish
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "espanol": "es",
    "español": "es",
    "castellano": "es",
    "es-es": "es",
    "es-419": "es",
    "es-mx": "es",
    # French
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "fr-fr": "fr",
    "fr-ca": "fr",
    # German
    "de": "de-1996",
    "ger": "de-1996",
    "deu": "de-1996",
    "german": "de-1996",
    "deutsch": "de-1996",
    "de-de": "de-1996",
    # Italian
    "it": "it",
    "ita": "it",
    "italian": "it",
    "italiano": "it",
    # Portuguese
    "pt": "pt",
    "por": "pt",
    "portuguese": "pt",
    "portugues": "pt",
    "português": "pt",
    "pt-br": "pt",
    "pt-pt": "pt",
    # Dutch
    "nl": "nl",
    "nld": "nl",
    "dut": "nl",
    "dutch": "nl",
    "nederlands": "nl",
    # Polish
    "pl": "pl",
    "pol": "pl",
    "polish": "pl",
    "polski": "pl",
    # Other languages ReadSight supports that a digest could plausibly select.
    "ca": "ca",
    "catalan": "ca",
    "cs": "cs",
    "czech": "cs",
    "da": "da",
    "danish": "da",
    "el": "el-monoton",
    "greek": "el-monoton",
    "fi": "fi",
    "finnish": "fi",
    "hu": "hu",
    "hungarian": "hu",
    "id": "id",
    "indonesian": "id",
    "no": "nb",
    "nb": "nb",
    "nb-no": "nb",
    "norwegian": "nb",
    "ro": "ro",
    "romanian": "ro",
    "ru": "ru",
    "russian": "ru",
    "sk": "sk",
    "slovak": "sk",
    "sv": "sv",
    "swedish": "sv",
    "tr": "tr",
    "turkish": "tr",
    "uk": "uk",
    "ukrainian": "uk",
}

#: When only a base code is known (``de``), prefer these suffixes in order
#: before falling back to the first supported variant alphabetically.
_VARIANT_SUFFIX_PREFERENCE: tuple[str, ...] = ("", "-1996", "-us", "-gbr", "-gb")


def _normalize(value: str) -> str:
    """Normalize a language label or code to a lookup key."""
    return re.sub(r"\s+", " ", value).strip().lower().replace("_", "-")


@lru_cache(maxsize=1)
def supported_language_codes() -> frozenset[str]:
    """Return every language code ReadSight can analyze."""
    try:
        return frozenset(rs.ReadSight.get_supported_languages())
    except Exception:  # pragma: no cover - defensive; library failure only
        return frozenset()


def is_supported(code: str | None) -> bool:
    """Return whether ``code`` is a ReadSight language code."""
    return bool(code) and code in supported_language_codes()


def to_readsight_code(value: str | None) -> str | None:
    """Map a project language label or code to a ReadSight language code.

    Returns ``None`` when the value cannot be mapped or is not supported by
    ReadSight. Already-valid ReadSight codes pass through unchanged, so the
    function is idempotent.
    """
    if value is None:
        return None
    normalized = _normalize(str(value))
    if not normalized:
        return None

    supported = supported_language_codes()
    if normalized in supported:
        return normalized

    mapped = LANGUAGE_ALIASES.get(normalized)
    if mapped is not None:
        return mapped if mapped in supported else None

    base = normalized.split("-", 1)[0]
    mapped_base = LANGUAGE_ALIASES.get(base)
    if mapped_base is not None:
        return mapped_base if mapped_base in supported else None

    variants = sorted(code for code in supported if code.startswith(f"{base}-"))
    for suffix in _VARIANT_SUFFIX_PREFERENCE:
        candidate = f"{base}{suffix}"
        if candidate in variants:
            return candidate
    return variants[0] if variants else None


@dataclass(frozen=True)
class LanguageResolution:
    """The outcome of resolving a digest's output language.

    ``code`` is ``None`` whenever the language is unknown. Callers must treat
    that as "readability not measurable" rather than assuming English.
    """

    requested: str | None
    code: str | None
    source: str
    supported: bool
    note: str | None = None

    @property
    def known(self) -> bool:
        return self.code is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "language_requested": self.requested,
            "language_code": self.code,
            "language_supported": self.supported,
            "language_source": self.source,
            "language_note": self.note,
        }


def resolve_language(
    candidates: Iterable[tuple[str | None, str]],
) -> LanguageResolution:
    """Resolve the digest output language from ordered candidates.

    Each candidate is ``(raw_value, source_label)``. The first candidate that
    carries a value is authoritative: if it cannot be mapped to a ReadSight
    code, resolution stops with ``unknown`` rather than falling through to a
    lower-priority candidate, so an explicit but unsupported language is never
    silently replaced.
    """
    ordered: Sequence[tuple[str | None, str]] = tuple(candidates)
    for raw, source in ordered:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        code = to_readsight_code(text)
        if code is None:
            return LanguageResolution(
                requested=text,
                code=None,
                source=source,
                supported=False,
                note=(
                    f"Language {text!r} from {source} could not be mapped to a "
                    "ReadSight language code; readability metrics are unavailable."
                ),
            )
        return LanguageResolution(
            requested=text,
            code=code,
            source=source,
            supported=True,
        )
    return LanguageResolution(
        requested=None,
        code=None,
        source="unknown",
        supported=False,
        note="No language metadata was available; readability metrics are unavailable.",
    )


def resolution_from_mapping(mapping: Mapping[str, str | None]) -> LanguageResolution:
    """Convenience helper: resolve from an ordered mapping of source -> value."""
    return resolve_language((value, source) for source, value in mapping.items())
