"""The central registry of supported callout *capabilities*, not a fixed vocabulary.

A callout is a small, optional, elevated component inside the editorial body. Before Phase 5
there was no supported semantic representation for one anywhere in the pipeline: the only stages
told about callouts were the ones told to *permit* or *remove* them, so no stage was accountable
for proposing or writing one, and neither digest ever produced one (baseline defect D7).

**Callouts are flexible.** Which signals a reader finds useful is a property of the *digest*, not
of the pipeline. One reader wants `🔥 TREND` and `🛠 PRACTICAL`; another wants `📷 TRY THIS` and
`📍 LOCAL & TIMELY`; a third invents something neither of them has. The pipeline must not close
that set. So this module deliberately does **not** enumerate the callout vocabulary.

What it owns is the part that is genuinely shared and domain-neutral:

* the **capabilities** a callout may use when rendered (bold, a citation pill, one link);
* the **limits** that keep a callout compact (how many per unit, how many per edition);
* the **shape** of a callout definition, so every stage agrees on what a callout *is*.

The digest's ``## Optional highlights`` section is the authoritative vocabulary. It names the
labels the reader wants and, in its own words, when each is warranted. :func:`parse_callout_definitions`
turns that section into definitions with stable identifiers, so the rest of the pipeline can
refer to a callout by id rather than by its rendered label — and a digest that invents a new
signal needs no code change.

This keeps domain-specific fields out of the reading-instructions contract, exactly as the
design requires: the contract stays four generic sections, and the vocabulary lives in the
digest's own prose.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Mapping

#: The rendering capabilities a callout may use. A callout definition's ``capabilities`` is a
#: subset of these, and the renderer may use only what the definition permits.
CAPABILITY_BOLD = "bold"
CAPABILITY_CITATION = "citation"
CAPABILITY_LINK = "link"

ALL_CAPABILITIES: tuple[str, ...] = (CAPABILITY_BOLD, CAPABILITY_CITATION, CAPABILITY_LINK)


@dataclass(frozen=True)
class CalloutLimits:
    """The compactness limits every callout is subject to.

    These are the pipeline's defaults, not a digest's preference. A digest may state a tighter
    total in its own section ("no more than four or five in total"); the effective limit is the
    tighter of the two.
    """

    max_per_unit: int = 1
    max_per_edition: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {"max_per_unit": self.max_per_unit, "max_per_edition": self.max_per_edition}


@dataclass(frozen=True)
class CalloutDefinition:
    """One callout signal a digest declares.

    ``id`` is a stable slug derived from the label, so the pipeline refers to a callout by id
    rather than by its rendered label. ``purpose`` is the digest's own statement of when the
    signal is warranted; it is never invented here.
    """

    id: str
    label: str
    emoji: str = ""
    purpose: str = ""
    capabilities: tuple[str, ...] = ALL_CAPABILITIES
    limits: CalloutLimits = field(default_factory=CalloutLimits)

    @property
    def display(self) -> str:
        """The label as a digest writes it, e.g. ``🔥 TREND``."""
        return f"{self.emoji} {self.label}".strip()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "emoji": self.emoji,
            "display": self.display,
            "purpose": self.purpose,
            "capabilities": list(self.capabilities),
            "limits": self.limits.to_dict(),
        }


def slugify(label: str) -> str:
    """A stable identifier for a callout label.

    ``🔥 TREND`` → ``trend``; ``LOCAL & TIMELY`` → ``local_timely``. The slug is what the
    approved semantic representation carries, so a callout is never identified by its rendered
    label — which may be localized or restyled without changing the callout's identity.
    """
    text = unicodedata.normalize("NFKD", label or "")
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip().lower())
    return text.strip("_")


#: An emoji or symbol run at the start of a label.
_LEADING_SYMBOL = re.compile(
    "^(?:[\U0001f000-\U0001faff\u2190-\u21ff\u2600-\u27bf\u2b00-\u2bff\uFE0F\u200d]+\\s*)+"
)
_BULLET = re.compile(r"^\s*[*\-+]\s+(?P<body>.+?)\s*$", re.MULTILINE)
_CODE_SPAN = re.compile(r"`([^`]+)`")
#: A digest may state a total limit in prose: "no more than four or five in total".
_TOTAL_LIMIT = re.compile(r"no more than\s+(?P<count>\w+)(?:\s+or\s+(?P<alt>\w+))?\s+in total", re.IGNORECASE)
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _split_label(raw: str) -> tuple[str, str]:
    """Split a raw label into ``(emoji, words)``."""
    text = (raw or "").strip()
    match = _LEADING_SYMBOL.match(text)
    if match:
        emoji = match.group(0).strip()
        words = text[match.end():].strip()
        return emoji, words
    return "", text


def _purpose_from_bullet(body: str, label: str) -> str:
    """The digest's own statement of when a signal is warranted, from its bullet text.

    The documented form is ``* `🔥 TREND`—an emerging pattern…``. Everything after the label
    and its dash is the purpose. When the label is not a code span, the leading label text is
    stripped so the purpose does not repeat it.
    """
    remainder = body
    span = _CODE_SPAN.search(remainder)
    if span:
        remainder = remainder[span.end():]
    else:
        # Strip the leading label (with its emoji) and any separator that follows it.
        stripped = _LEADING_SYMBOL.sub("", remainder).strip()
        if stripped.upper().startswith(label.upper()):
            remainder = stripped[len(label):]
    remainder = re.sub(r"^\s*[—–\-:]\s*", "", remainder).strip()
    return remainder


def parse_callout_definitions(highlights_text: str | None) -> tuple[CalloutDefinition, ...]:
    """Parse a digest's ``## Optional highlights`` section into callout definitions.

    The section is free text. A callout is declared by a bullet whose label is a code span
    (the documented form) or the leading text before a dash. The digest's own wording after the
    label becomes the definition's purpose. Nothing is invented: a section that declares no
    callout yields no definitions, and a digest that invents a new signal needs no code change.
    """
    if not highlights_text:
        return ()
    edition_limit = _edition_limit(highlights_text)
    definitions: list[CalloutDefinition] = []
    seen: set[str] = set()

    def add(raw_label: str, purpose: str) -> None:
        emoji, words = _split_label(raw_label)
        if not words:
            return
        identifier = slugify(words)
        if not identifier or identifier in seen:
            return
        seen.add(identifier)
        definitions.append(
            CalloutDefinition(
                id=identifier,
                label=words,
                emoji=emoji,
                purpose=purpose.strip(),
                limits=CalloutLimits(max_per_unit=1, max_per_edition=edition_limit),
            )
        )

    for match in _BULLET.finditer(highlights_text):
        body = match.group("body")
        span = _CODE_SPAN.search(body)
        if span:
            add(span.group(1), _purpose_from_bullet(body, span.group(1)))
        else:
            head = re.split(r"[—–-]", body, maxsplit=1)[0]
            _, words = _split_label(head)
            add(head, _purpose_from_bullet(body, words))
    return tuple(definitions)


def _edition_limit(highlights_text: str) -> int | None:
    """A total limit the digest states in prose, or ``None``."""
    match = _TOTAL_LIMIT.search(highlights_text)
    if not match:
        return None
    for key in ("alt", "count"):
        token = (match.group(key) or "").strip().lower()
        if token.isdigit():
            return int(token)
        if token in _WORD_NUMBERS:
            return _WORD_NUMBERS[token]
    return None


@dataclass
class CalloutRegistry:
    """The callouts one digest authorizes, resolved from its own section.

    The registry is per-digest because the vocabulary is per-digest. It holds the definitions
    the digest declared and answers the questions the rest of the pipeline asks: is this callout
    authorized, what is its stable id, and what are its limits.
    """

    definitions: tuple[CalloutDefinition, ...] = ()
    source: str = ""

    @property
    def available(self) -> bool:
        return bool(self.definitions)

    def by_id(self, identifier: str | None) -> CalloutDefinition | None:
        if not identifier:
            return None
        wanted = identifier.strip().lower()
        for definition in self.definitions:
            if definition.id == wanted:
                return definition
        return None

    def by_label(self, label: str) -> CalloutDefinition | None:
        _, words = _split_label(label)
        wanted = slugify(words)
        return self.by_id(wanted)

    def ids(self) -> tuple[str, ...]:
        return tuple(definition.id for definition in self.definitions)

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "capabilities": list(ALL_CAPABILITIES),
            "definitions": [definition.to_dict() for definition in self.definitions],
        }


def registry_for(highlights_text: str | None, *, source: str = "") -> CalloutRegistry:
    """Build the registry for one digest from its ``## Optional highlights`` section."""
    return CalloutRegistry(
        definitions=parse_callout_definitions(highlights_text),
        source=source,
    )


def registry_manifest() -> dict[str, object]:
    """The domain-neutral part of the registry, for the run record and the render stage.

    This is what is genuinely shared: the capabilities a callout may use and the default limits.
    The vocabulary itself is per-digest and is recorded from the digest's own section.
    """
    return {
        "capabilities": list(ALL_CAPABILITIES),
        "default_limits": CalloutLimits().to_dict(),
    }


__all__ = [
    "ALL_CAPABILITIES",
    "CAPABILITY_BOLD",
    "CAPABILITY_CITATION",
    "CAPABILITY_LINK",
    "CalloutDefinition",
    "CalloutLimits",
    "CalloutRegistry",
    "parse_callout_definitions",
    "registry_for",
    "registry_manifest",
    "slugify",
]