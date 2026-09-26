"""Authoritative rendering values: the run key and the deterministic template values.

Python port of ``src/editorial/rendering/values.mjs``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping

from ..validation.copy_verify import split_catalog, word_count

#: Minutes-per-word basis for estimating the digest's own reading time, stated by
#: ``system/workflow.md`` and ``system/html-rendering.md``.
WORDS_PER_MINUTE = 225

#: Outcome wording that means the item was *not* substantively read.
NON_SUBSTANTIVE_OUTCOMES: tuple[str, ...] = (
    "not_read",
    "unread",
    "not_selected",
    "skipped",
    "duplicate",
    "inaccessible",
    "excluded",
    "pending",
    "discarded",
    "unsupported",
    "not_available",
)

_RUN_KEY_MARKER = re.compile(r"run-key:\s*(.+?)\s*-->")


def resolve_run_key(*, corpus: Any, digest_id: str, style: str) -> dict[str, str]:
    """Resolve the authoritative run key for a run.

    Order: the orchestrator's precomputed marker, then the corpus ``run_key``, then a
    deterministic derivation from the digest ID and the sorted admitted Gmail message IDs.
    """
    delivery = corpus.get("delivery") if isinstance(corpus, Mapping) else None
    marker = delivery.get("invisible_html_run_marker") if isinstance(delivery, Mapping) else None
    if isinstance(marker, str):
        match = _RUN_KEY_MARKER.search(marker)
        if match and match.group(1).strip():
            return {"runKey": match.group(1).strip(), "source": "delivery.invisible_html_run_marker"}
    if isinstance(corpus, Mapping) and isinstance(corpus.get("run_key"), str) and corpus["run_key"].strip():
        return {"runKey": corpus["run_key"].strip(), "source": "corpus.run_key"}
    message_ids: list[str] = []
    sources = corpus.get("sources") if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list) else []
    for source in sources:
        value = source.get("originating_gmail_message_id") if isinstance(source, Mapping) else None
        if value:
            message_ids.append(str(value))
    emails = corpus.get("source_emails") if isinstance(corpus, Mapping) and isinstance(corpus.get("source_emails"), list) else []
    for email in emails:
        value = email.get("originating_gmail_message_id") if isinstance(email, Mapping) else None
        if value:
            message_ids.append(str(value))
    unique = sorted(set(message_ids))
    return {
        "runKey": f"{digest_id}-{style}-{'+'.join(unique) if unique else 'no-messages'}",
        "source": "derived:digest+sorted-message-ids",
    }


def _is_substantively_read(source: Mapping[str, Any]) -> bool:
    outcome = str(source.get("reading_outcome") or "").strip().lower()
    if not outcome:
        return True  # no claim either way; the corpus listing is the claim
    return not any(marker in outcome for marker in NON_SUBSTANTIVE_OUTCOMES)


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def resolve_rendering_values(
    *,
    corpus: Any,
    digest_id: str,
    digest_name: str | None,
    style: str,
    language: str,
    body_prose: str,
) -> dict[str, Any]:
    """Resolve every authoritative value the rendering template needs.

    The render stage is a presentation layer: it must not invent a date, a reading time, or a
    digest name. Those values are deterministic here, so the runner computes them and supplies
    them. Every value carries its source so an audit can tell a measured number from a derived
    one, and a value that genuinely cannot be resolved is omitted rather than guessed.
    """
    values: dict[str, Any] = {
        "digest_id": digest_id,
        "digest_name": digest_name,
        "style": style,
        "language": language,
    }
    notes: list[str] = []

    # --- html lang ---------------------------------------------------------------------
    declared_html_lang = corpus.get("html_lang") if isinstance(corpus, Mapping) else None
    declared_html_lang = declared_html_lang.strip() if isinstance(declared_html_lang, str) else ""
    if declared_html_lang:
        values["html_lang"] = declared_html_lang
        values["html_lang_source"] = "corpus.html_lang"
    else:
        values["html_lang_instruction"] = "Resolve a valid BCP 47 tag for <html lang> from the declared language above."

    # --- date -------------------------------------------------------------------------
    delivery = corpus.get("delivery") if isinstance(corpus, Mapping) else None
    subject = delivery.get("subject") if isinstance(delivery, Mapping) else None
    subject = subject.strip() if isinstance(subject, str) else None
    if subject:
        values["delivery_subject"] = subject
        values["date_source"] = "delivery.subject"
    acquired_at = _parse_iso(corpus.get("acquisition_time") if isinstance(corpus, Mapping) else None)
    if acquired_at is not None:
        values["date_iso"] = acquired_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        values.setdefault("date_source", "corpus.acquisition_time")
    else:
        sources = corpus.get("sources") if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list) else []
        received = sorted(
            (parsed for parsed in (_parse_iso(source.get("received_at")) for source in sources if isinstance(source, Mapping)) if parsed),
            reverse=True,
        )
        if received:
            values["date_iso"] = received[0].astimezone(timezone.utc).strftime("%Y-%m-%d")
            values.setdefault("date_source", "latest source received_at")
        elif subject:
            values["date_instruction"] = (
                "The digest date is inside the authoritative delivery subject above. Take it from there "
                "rather than formatting a date independently, and reuse the subject's own localization."
            )
        else:
            notes.append(
                "No digest date could be resolved: the corpus carries no delivery subject, acquisition time, or source timestamps."
            )

    # --- reading time -----------------------------------------------------------------
    sources = corpus.get("sources") if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list) else []
    source_minutes = 0.0
    counted = 0
    for source in sources:
        if not isinstance(source, Mapping) or not _is_substantively_read(source):
            continue
        raw = source.get("reading_time_minutes", source.get("reading_minutes", 0))
        try:
            minutes = float(raw)
        except (TypeError, ValueError):
            continue
        if minutes <= 0:
            continue
        source_minutes += minutes
        counted += 1
    if counted > 0:
        values["reviewed_source_minutes"] = round(source_minutes, 1)
        values["reviewed_source_count"] = counted
        values["reviewed_source_basis"] = "sum of recorded reading times for substantively read sources"
    else:
        notes.append(
            "No reviewed-source reading time could be resolved: no source records a substantive reading outcome with a reading time. "
            "The capsule must use the contract's degraded digest-only form rather than a partially filled source → digest pair."
        )

    # --- the digest's own reading time, and the saving ---------------------------------
    words = word_count(split_catalog(body_prose or "")["body"])
    if words > 0:
        values["digest_body_words"] = words
        values["digest_minutes"] = round(words / WORDS_PER_MINUTE, 1)
        values["digest_minutes_basis"] = (
            f"{words} body words at {WORDS_PER_MINUTE} words per minute, excluding the source catalog"
        )
        if "reviewed_source_minutes" in values:
            saved = values["reviewed_source_minutes"] - values["digest_minutes"]
            if saved > 0:
                values["time_saved_minutes"] = round(saved, 1)
            else:
                notes.append("The reviewed-source total is not longer than the digest, so no time saved can be stated.")
    else:
        notes.append("The approved prose was unavailable, so the digest reading time could not be computed.")

    return {"values": values, "notes": notes}


def describe_reading_time(values: Mapping[str, Any]) -> dict[str, Any]:
    """The two reading-time halves of the capsule, plus the saving."""
    return {
        "reviewed_source_minutes": values.get("reviewed_source_minutes"),
        "reviewed_source_count": values.get("reviewed_source_count"),
        "digest_body_words": values.get("digest_body_words"),
        "digest_minutes": values.get("digest_minutes"),
        "time_saved_minutes": values.get("time_saved_minutes"),
    }


__all__ = ["WORDS_PER_MINUTE", "resolve_run_key", "resolve_rendering_values", "describe_reading_time"]