"""Deterministic publication checks and the copy-pass diff guard.

Python port of ``src/editorial/validation/copy-verify.mjs``.

COPY / VERIFY is deliberately not a writing stage. Most of what it verifies — citation
integrity, catalogue consistency, verbatim source titles, structure, Markdown correctness,
length sanity, renderability, and the leak guard — can be decided mechanically, and a
mechanical check cannot be talked out of a finding by fluent prose.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from ...config.budgets import STYLE_BUDGET

LEAK_MARKERS: tuple[str, ...] = (
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "cache_hit_ratio",
    "reasoning_tokens",
    "estimated_cost_usd",
    "cost_usd",
    "run-summary",
    "run_summary",
    "cost-ledger",
    "cost_ledger",
    "verification.json",
    "verification.md",
    "billing_band",
    "if_all_peak",
    "if_nothing_cached",
    "corpus-context",
    "corpus_policy",
    "cache_miss_tokens",
)

CATALOG_HEADINGS: tuple[str, ...] = (
    "sources",
    "source catalog",
    "sources catalog",
    "bibliography",
    "references",
    "fuentes",
    "sources citees",
    "sources citées",
    "quellen",
    "fonti",
)

PLACEHOLDER_MARKERS: tuple[str, ...] = ("{{", "}}", "TODO", "TBD", "LOREM IPSUM", "PLACEHOLDER", "XXX")


# ---------------------------------------------------------------------------------------
# Text surgery
# ---------------------------------------------------------------------------------------


def normalize_newlines(text: Any) -> str:
    return str(text if text is not None else "").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


_FRONTMATTER = re.compile(r"^---[ \t]*\n[\s\S]*?\n---[ \t]*(?:\n|$)")


def strip_frontmatter(text: str) -> str:
    match = _FRONTMATTER.match(text)
    return text[match.end() :] if match else text


_HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]*(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)


def heading_texts(text: str) -> list[dict[str, Any]]:
    results = []
    for match in _HEADING_PATTERN.finditer(text):
        results.append(
            {
                "index": match.start(),
                "level": len(match.group(1)),
                "title": re.sub(r"[*_`]+", "", match.group(2)).strip(),
            }
        )
    return results


def split_catalog(text: str) -> dict[str, Any]:
    """Split the trailing bibliographic catalogue from the editorial body.

    Cutting in the wrong place silently changes the word count every length check depends
    on, so the cut only happens on an exact normalized heading match.
    """
    headings = heading_texts(text)
    for heading in reversed(headings):
        if heading["title"].lower() in CATALOG_HEADINGS:
            return {
                "body": text[: heading["index"]].rstrip(),
                "catalog": text[heading["index"] :].strip(),
                "heading": heading["title"],
                "detection": "heading",
            }
    return {"body": text.rstrip(), "catalog": "", "heading": None, "detection": "none"}


_CITATION = re.compile(r"\[(\d{1,3}(?:\s*[,–\-]\s*\d{1,3})*)\]")


def extract_citations(text: str) -> set[int]:
    """Citation markers: ``[12]``, ``[12, 13]``, ``[12][13]``, ``[12–14]``."""
    numbers: set[int] = set()
    for match in _CITATION.finditer(text):
        for part in re.split(r"[,–\-]", match.group(1)):
            try:
                value = int(part.strip())
            except ValueError:
                continue
            if value > 0:
                numbers.add(value)
    return numbers


_CATALOG_ROW = re.compile(r"^(\d{1,3})[.)]\s+(.*)$")
_CATALOG_LINK = re.compile(r"^\[([^\]]+)\]\(([^)\s]+)")


def extract_catalog_rows(catalog: str) -> dict[str, Any]:
    """Catalogue rows: ``12. [Title](https://…) · 7 min · Reviewed``, ``12. Title``."""
    rows = []
    malformed = []
    for line in normalize_newlines(catalog).split("\n"):
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#") or trimmed.startswith("|"):
            continue
        match = _CATALOG_ROW.match(trimmed)
        if not match:
            continue
        number = int(match.group(1))
        rest = match.group(2).strip()
        if not rest:
            malformed.append({"number": number, "line": trimmed})
            continue
        link = _CATALOG_LINK.match(rest)
        rows.append(
            {
                "number": number,
                "raw": rest,
                "title": link.group(1).strip() if link else None,
                "url": link.group(2) if link else None,
            }
        )
    return {"rows": rows, "malformed": malformed}


_CODE_BLOCK = re.compile(r"```[\s\S]*?```")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MARKUP = re.compile(r"[#*_>`~|]")


def word_count(text: str) -> int:
    value = normalize_newlines(text)
    value = _CODE_BLOCK.sub(" ", value)
    value = _IMAGE.sub(" ", value)
    value = _LINK.sub(r"\1", value)
    value = _MARKUP.sub(" ", value)
    return len([token for token in re.split(r"\s+", value) if token])


def paragraph_count(text: str) -> int:
    return len([block for block in (part.strip() for part in re.split(r"\n{2,}", normalize_newlines(text))) if block])


def parse_style_interface(style_text: str) -> dict[str, str]:
    """Parse a style's ``## Style interface`` markdown table into a dimension → value map."""
    body = split_catalog(style_text)["body"]
    lines = normalize_newlines(body).split("\n")
    in_interface = False
    dimensions: dict[str, str] = {}
    for line in lines:
        heading = re.match(r"^##\s+(.*?)\s*$", line)
        if heading:
            in_interface = heading.group(1).strip().lower() == "style interface"
            continue
        if not in_interface:
            continue
        trimmed = line.strip()
        if not trimmed.startswith("|"):
            continue
        cells = [cell.strip() for cell in trimmed.split("|")]
        if len(cells) < 4:
            continue
        name = cells[1].replace("**", "").strip().lower()
        value = cells[2].replace("**", "").strip()
        if not name or re.fullmatch(r"-+", name) or name == "dimension":
            continue
        dimensions[name] = value
    return dimensions


def catalog_required(style_text: str) -> bool | None:
    dimensions = parse_style_interface(style_text)
    value = dimensions.get("source catalog")
    if not value:
        return None  # unknown
    return not re.fullmatch(r"none", value, re.IGNORECASE)


# ---------------------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------------------


def _check(check_id: str, status: str, note: str, details: Any = None) -> dict[str, Any]:
    value: dict[str, Any] = {"id": check_id, "status": status, "note": note}
    if details is not None:
        value["details"] = details
    return value


def run_deterministic_checks(
    *,
    prose: str,
    corpus: Any,
    frame: Any = None,
    style_text: str = "",
    language: str = "English",
    style: str | None = None,
    catalogue_required: bool | None = None,
    budget: Any = None,
    exempt_length: bool = False,
) -> dict[str, Any]:
    """Run every deterministic publication check over one artifact.

    ``status`` is ``pass``, ``warn``, ``fail`` or ``exempt``. A ``fail`` is a publication
    problem the copy pass may be able to correct; it is reported, never fixed silently here.
    """
    checks: list[dict[str, Any]] = []
    document = normalize_newlines(strip_frontmatter(normalize_newlines(prose)))
    sources = corpus.get("sources") if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list) else []
    corpus_numbers = set()
    titles_by_number: dict[int, str] = {}
    for source in sources:
        if not isinstance(source, Mapping) or source.get("source_number") is None:
            continue
        try:
            number = int(source["source_number"])
        except (TypeError, ValueError):
            continue
        corpus_numbers.add(number)
        titles_by_number[number] = str(source.get("title") or "").strip()

    # --- structure -----------------------------------------------------------------
    headings = heading_texts(document)
    if not document.strip():
        checks.append(_check("structure:non-empty", "fail", "artifact is empty"))
    elif len(headings) == 0:
        checks.append(_check("structure:headings", "fail", "artifact contains no headings"))
    else:
        checks.append(_check("structure:headings", "pass", f"{len(headings)} heading(s)"))
    html_tags = len(re.findall(r"</?(?:script|style|div|span|table|td|tr|p|br)\b[^>]*>", document, re.IGNORECASE))
    checks.append(
        _check("structure:no-html", "pass", "no HTML markup in the Markdown artifact")
        if html_tags == 0
        else _check("structure:no-html", "fail", f"{html_tags} HTML tag(s) present in the Markdown artifact")
    )
    fences = len(re.findall(r"^\s*```", document, re.MULTILINE))
    checks.append(
        _check("structure:no-code-fence", "pass", "no code fences")
        if fences == 0
        else _check("structure:no-code-fence", "warn", f"{fences} code fence marker(s) present")
    )
    placeholders = [marker for marker in PLACEHOLDER_MARKERS if marker.upper() in document.upper()]
    checks.append(
        _check("structure:no-placeholder", "pass", "no unresolved placeholder text")
        if not placeholders
        else _check("structure:no-placeholder", "fail", f"placeholder text present: {', '.join(placeholders)}")
    )

    # --- citations -----------------------------------------------------------------
    citations = extract_citations(document)
    unknown_citations = sorted(value for value in citations if value not in corpus_numbers)
    checks.append(
        _check("citations:resolve", "pass", f"{len(citations)} distinct citation number(s), all in the corpus")
        if not unknown_citations
        else _check(
            "citations:resolve",
            "fail",
            f"citation number(s) not in the corpus: {', '.join(map(str, unknown_citations))}",
            {"unknown": unknown_citations},
        )
    )

    # --- catalogue -----------------------------------------------------------------
    split = split_catalog(document)
    body, catalog, detection = split["body"], split["catalog"], split["detection"]
    extracted = extract_catalog_rows(catalog)
    rows, malformed = extracted["rows"], extracted["malformed"]
    catalogue_numbers = [row["number"] for row in rows]
    duplicate_numbers = [value for index, value in enumerate(catalogue_numbers) if value in catalogue_numbers[:index]]
    required = catalogue_required if catalogue_required is not None else catalog_required(style_text)

    if required is True and not catalog:
        checks.append(_check("catalog:present", "fail", "the style requires a source catalogue and none was found"))
    elif required is True:
        checks.append(_check("catalog:present", "pass", f"catalogue detected ({detection}) with {len(rows)} row(s)"))
    elif required is False:
        checks.append(_check("catalog:not-required", "pass", "the style declares no source catalogue"))
    else:
        checks.append(_check("catalog:unknown", "warn", "the style interface declares no catalogue dimension"))
    if duplicate_numbers:
        checks.append(
            _check("catalog:duplicates", "fail", f"duplicate catalogue entr(ies): {', '.join(map(str, sorted(set(duplicate_numbers))))}")
        )
    elif rows:
        checks.append(_check("catalog:duplicates", "pass", "no duplicate catalogue entries"))
    if malformed:
        checks.append(_check("catalog:well-formed", "fail", f"{len(malformed)} catalogue row(s) have no title"))
    uncatalogued = sorted(
        value for value in citations if value in corpus_numbers and rows and value not in catalogue_numbers
    )
    if rows and uncatalogued:
        checks.append(
            _check(
                "catalog:covers-citations",
                "fail",
                f"cited source(s) missing from the catalogue: {', '.join(map(str, uncatalogued))}",
                {"missing": uncatalogued},
            )
        )
    elif rows:
        checks.append(_check("catalog:covers-citations", "pass", "every cited source appears in the catalogue"))

    # --- provenance: verbatim titles ------------------------------------------------
    title_mismatches = []
    for row in rows:
        if not row["title"]:
            continue
        corpus_title = titles_by_number.get(row["number"])
        if corpus_title is None:
            continue
        if row["title"] != corpus_title:
            title_mismatches.append({"number": row["number"], "artifact": row["title"], "corpus": corpus_title})
    checks.append(
        _check("provenance:titles-verbatim", "pass", "catalogue titles match the reviewed source titles verbatim")
        if not title_mismatches
        else _check(
            "provenance:titles-verbatim",
            "fail",
            f"{len(title_mismatches)} catalogue title(s) differ from the reviewed source title",
            {"mismatches": title_mismatches},
        )
    )

    # --- frame authority ------------------------------------------------------------
    declared = narrative_evidence_numbers(frame)
    if declared:
        body_citations = extract_citations(body)
        undeclared = sorted(value for value in body_citations if value not in declared and value in corpus_numbers)
        checks.append(
            _check("frame:citations-declared", "pass", "every narrative citation was declared by a retained frame unit")
            if not undeclared
            else _check(
                "frame:citations-declared",
                "warn",
                f"narrative source(s) not declared by any retained frame unit: {', '.join(map(str, undeclared))}",
                {"undeclared": undeclared, "declared": sorted(declared)},
            )
        )

    # --- length ---------------------------------------------------------------------
    effective_budget = budget if budget is not None else (STYLE_BUDGET.get(style) if style else None)
    if exempt_length:
        measured = (
            f"{word_count(body)} body words against a {effective_budget.min}-{effective_budget.max} target"
            if effective_budget and effective_budget.unit == "document"
            else "no document budget applies to this style"
        )
        checks.append(
            _check(
                "length:budget",
                "exempt",
                f"exempt: FRAME declared a catalog-only edition, so the body is intentionally short ({measured})",
            )
        )
    elif effective_budget is None:
        checks.append(_check("length:budget", "warn", f"no length budget is defined for style {style or '(none)'}"))
    elif effective_budget.unit == "document":
        words = word_count(body)
        minimum, maximum = effective_budget.min, effective_budget.max
        checks.append(
            _check("length:budget", "pass", f"{words} body words against a {minimum}-{maximum} target")
            if minimum * 0.75 <= words <= maximum * 1.25
            else _check("length:budget", "warn", f"{words} body words against a {minimum}-{maximum} target")
        )
    else:
        entries = split_source_entries(body)
        outside = [
            entry
            for entry in entries
            if entry["words"] < effective_budget.min * 0.6 or entry["words"] > effective_budget.max * 1.6
        ]
        checks.append(
            _check(
                "length:budget",
                "pass",
                f"{len(entries)} entries within the {effective_budget.min}-{effective_budget.max} word band",
            )
            if not outside
            else _check(
                "length:budget",
                "warn",
                f"{len(outside)} of {len(entries)} entries fall outside the {effective_budget.min}-{effective_budget.max} word band",
                {"entries": outside[:8]},
            )
        )

    # --- renderability and leak guard ------------------------------------------------
    leaks = [marker for marker in LEAK_MARKERS if marker in document]
    checks.append(
        _check("renderability:no-leak", "pass", "no operational or cost data present")
        if not leaks
        else _check("renderability:no-leak", "fail", f"operational data present: {', '.join(leaks)}")
    )
    control_chars = len([character for character in document if ord(character) < 9])
    checks.append(
        _check("renderability:characters", "pass", "no control characters")
        if control_chars == 0
        else _check("renderability:characters", "fail", f"{control_chars} control character(s) present")
    )

    # --- markdown correctness -------------------------------------------------------
    markdown = []
    bold_markers = len(re.findall(r"\*\*", document))
    if bold_markers % 2 != 0:
        markdown.append("unbalanced ** emphasis markers")
    open_links = len(re.findall(r"\]\(", document))
    close_links = len(re.findall(r"\)", document))
    if open_links > close_links:
        markdown.append("link syntax opened without closing parenthesis")
    checks.append(
        _check("markdown:well-formed", "pass", "emphasis and link syntax is balanced")
        if not markdown
        else _check("markdown:well-formed", "warn", "; ".join(markdown))
    )

    # --- output language ------------------------------------------------------------
    declared_language = str(language if language is not None else "").strip()
    if not declared_language or re.fullmatch(r"english", declared_language, re.IGNORECASE):
        checks.append(_check("language:output", "pass", f"output language is {declared_language or 'English'}"))
    else:
        letters = [character for character in document if character.isalpha()]
        ascii_letters = len([character for character in letters if ord(character) < 128])
        ratio = (ascii_letters / len(letters)) if letters else 1
        checks.append(
            _check(
                "language:output",
                "warn",
                f"advisory: {ratio * 100:.0f}% of letters are ASCII for a {declared_language} digest, which may indicate the localization was not applied or was applied in part",
            )
            if ratio > 0.97
            else _check("language:output", "pass", f"artifact is {ratio * 100:.0f}% ASCII for a {declared_language} digest")
        )

    counts = {
        "pass": len([item for item in checks if item["status"] == "pass"]),
        "warn": len([item for item in checks if item["status"] == "warn"]),
        "fail": len([item for item in checks if item["status"] == "fail"]),
        "exempt": len([item for item in checks if item["status"] == "exempt"]),
    }
    return {
        "checks": checks,
        "counts": counts,
        "citations": sorted(citations),
        "catalogue_numbers": catalogue_numbers,
        "body_words": word_count(body),
        "total_words": word_count(document),
        "catalogue_detection": detection,
    }


def split_source_entries(body: str) -> list[dict[str, Any]]:
    """Split a body into per-source entries by heading, for per-entry length budgets."""
    headings = heading_texts(body)
    entries = []
    for index, heading in enumerate(headings):
        start = heading["index"]
        end = headings[index + 1]["index"] if index + 1 < len(headings) else len(body)
        entries.append({"title": heading["title"], "words": word_count(body[start:end])})
    return entries


# ---------------------------------------------------------------------------------------
# Copy-pass guard
# ---------------------------------------------------------------------------------------


def guard_copy_pass(
    *, before: str, after: str, budget: Any = None, catalogue_required: bool | None = None
) -> dict[str, Any]:
    """Decide whether a copy pass may replace its input.

    COPY / VERIFY "must not substantially compress, reframe, restructure, remove examples,
    change arguments, or invent claims". Every one of those is measurable from the two
    artifacts, so the pass is accepted only when none of them happened. A rejected pass is
    not a failure: the input prose is used unchanged.
    """
    reasons: list[str] = []
    original = normalize_newlines(strip_frontmatter(normalize_newlines(before)))
    revised = normalize_newlines(strip_frontmatter(normalize_newlines(after)))

    if not revised.strip():
        return {"accepted": False, "reasons": ["copy pass returned an empty artifact"], "deltas": {}}

    before_split = split_catalog(original)
    after_split = split_catalog(revised)
    before_words = word_count(before_split["body"])
    after_words = word_count(after_split["body"])
    delta_words = after_words - before_words
    delta_ratio = (delta_words / before_words) if before_words else 0

    if delta_ratio < -0.03:
        reasons.append(f"body shrank by {abs(delta_ratio) * 100:.1f}% ({before_words} → {after_words} words)")
    if delta_ratio > 0.05:
        reasons.append(f"body grew by {delta_ratio * 100:.1f}% ({before_words} → {after_words} words)")

    before_headings = [item["title"].lower() for item in heading_texts(before_split["body"])]
    after_headings = [item["title"].lower() for item in heading_texts(after_split["body"])]
    removed = [title for title in before_headings if title not in after_headings]
    if removed:
        reasons.append(f"headings removed: {' | '.join(removed[:4])}")

    before_citations = extract_citations(original)
    after_citations = extract_citations(revised)
    added = sorted(value for value in after_citations if value not in before_citations)
    dropped = sorted(value for value in before_citations if value not in after_citations)
    if added:
        reasons.append(f"citations introduced: {', '.join(map(str, added))}")
    if dropped:
        reasons.append(f"citations removed: {', '.join(map(str, dropped))}")

    before_rows = [row["number"] for row in extract_catalog_rows(before_split["catalog"])["rows"]]
    after_rows = [row["number"] for row in extract_catalog_rows(after_split["catalog"])["rows"]]
    if before_rows and len(before_rows) != len(after_rows):
        reasons.append(f"catalogue row count changed: {len(before_rows)} → {len(after_rows)}")

    before_paragraphs = paragraph_count(before_split["body"])
    after_paragraphs = paragraph_count(after_split["body"])
    if after_paragraphs < before_paragraphs - 1:
        reasons.append(f"paragraphs removed: {before_paragraphs} → {after_paragraphs}")

    if budget and budget.unit == "document" and after_words and (after_words < budget.min * 0.5 or after_words > budget.max * 1.5):
        reasons.append(f"{after_words} body words is outside any plausible range for the {budget.min}-{budget.max} target")
    if catalogue_required is True and before_split["catalog"] and not after_split["catalog"]:
        reasons.append("the copy pass removed the source catalogue")
    if any(marker in revised for marker in LEAK_MARKERS) and not any(marker in original for marker in LEAK_MARKERS):
        reasons.append("the copy pass introduced operational data")

    return {
        "accepted": len(reasons) == 0,
        "reasons": reasons,
        "deltas": {
            "body_words_before": before_words,
            "body_words_after": after_words,
            "delta_words": delta_words,
            "delta_ratio": round(delta_ratio, 4),
            "paragraphs_before": before_paragraphs,
            "paragraphs_after": after_paragraphs,
            "citations_before": sorted(before_citations),
            "citations_after": sorted(after_citations),
        },
    }


# ---------------------------------------------------------------------------------------
# Frame declarations
# ---------------------------------------------------------------------------------------

UNIT_KEYS: tuple[str, ...] = (
    "editorial_units",
    "units",
    "threads",
    "synthesis_threads",
    "full_selections",
    "entries",
    "discoveries",
)
UNIT_SOURCE_KEYS: tuple[str, ...] = ("selected_source_numbers", "source_numbers", "sources")

#: Dispositions that mean the unit is not part of the narrative the draft stage writes.
NON_NARRATIVE_DISPOSITIONS: tuple[str, ...] = ("split", "demote", "cut")


def _collect_units(frame: Any) -> list[Mapping[str, Any]]:
    units: list[Any] = []
    if isinstance(frame, Mapping):
        for key in UNIT_KEYS:
            if isinstance(frame.get(key), list):
                units.extend(frame[key])
        nested = frame.get("editorial_frame")
        if isinstance(nested, Mapping):
            for key in UNIT_KEYS:
                if isinstance(nested.get(key), list):
                    units.extend(nested[key])
    return [unit for unit in units if isinstance(unit, Mapping)]


def _unit_source_numbers(unit: Mapping[str, Any]) -> set[int]:
    numbers: set[int] = set()

    def add(value: Any) -> None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return
        if number > 0:
            numbers.add(number)

    for key in UNIT_SOURCE_KEYS:
        if isinstance(unit.get(key), list):
            for value in unit[key]:
                add(value)
    return numbers


def narrative_evidence_numbers(frame: Any) -> set[int]:
    """The sources the narrative is allowed to use: the union of the **retained** units'
    ``selected_source_numbers``.

    This is the whole of what the draft stage receives, and it is deliberately the only
    declaration that counts. It excludes units that were set aside, the citation map, and
    ``catalog_only.selected``.
    """
    numbers: set[int] = set()
    if not isinstance(frame, Mapping):
        return numbers
    for unit in _collect_units(frame):
        disposition = unit.get("disposition", "keep")
        if disposition in NON_NARRATIVE_DISPOSITIONS:
            continue
        numbers |= _unit_source_numbers(unit)
    return numbers


def evidence_refs_outside_selection(frame: Any) -> set[int]:
    """Source numbers a retained unit's ``evidence_refs`` names but its
    ``selected_source_numbers`` does not."""
    outside: set[int] = set()
    if not isinstance(frame, Mapping):
        return outside
    for unit in _collect_units(frame):
        if unit.get("disposition", "keep") in NON_NARRATIVE_DISPOSITIONS:
            continue
        declared = _unit_source_numbers(unit)
        if not isinstance(unit.get("evidence_refs"), list):
            continue
        for reference in unit["evidence_refs"]:
            if not isinstance(reference, Mapping):
                continue
            try:
                number = int(reference.get("source_number"))
            except (TypeError, ValueError):
                continue
            if number > 0 and number not in declared:
                outside.add(number)
    return outside


def catalog_provenance_numbers(frame: Any) -> set[int]:
    """Every source number the frame records catalogue provenance for.

    Separate from the narrative selection because the two answer different questions: the
    narrative projection is "what may the writer cite", and this is "what must the catalogue
    list".
    """
    numbers: set[int] = set()
    if not isinstance(frame, Mapping):
        return numbers
    for unit in _collect_units(frame):
        numbers |= _unit_source_numbers(unit)
    citation_map = frame.get("citation_map")
    if isinstance(citation_map, Mapping):
        for key in citation_map:
            try:
                number = int(key)
            except (TypeError, ValueError):
                continue
            if number > 0:
                numbers.add(number)
    catalog_only = frame.get("catalog_only")
    if isinstance(catalog_only, Mapping):
        if isinstance(catalog_only.get("selected"), list):
            for value in catalog_only["selected"]:
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    continue
                if number > 0:
                    numbers.add(number)
        if isinstance(catalog_only.get("entries"), list):
            for entry in catalog_only["entries"]:
                raw = entry.get("source_number", entry) if isinstance(entry, Mapping) else entry
                try:
                    number = int(raw)
                except (TypeError, ValueError):
                    continue
                if number > 0:
                    numbers.add(number)
    return numbers


def summarize_frame_unit_declarations(frame: Any) -> list[dict[str, Any]]:
    """Retained units, with the evidence each declares."""
    units = []
    for unit in _collect_units(frame):
        disposition = unit.get("disposition", "keep")
        units.append(
            {
                "unit_id": unit.get("unit_id", unit.get("label", unit.get("id"))),
                "disposition": disposition,
                "retained": disposition not in NON_NARRATIVE_DISPOSITIONS,
                "selected_source_numbers": sorted(_unit_source_numbers(unit)),
            }
        )
    return units


__all__ = [
    "LEAK_MARKERS",
    "CATALOG_HEADINGS",
    "normalize_newlines",
    "strip_frontmatter",
    "heading_texts",
    "split_catalog",
    "extract_citations",
    "extract_catalog_rows",
    "word_count",
    "paragraph_count",
    "parse_style_interface",
    "catalog_required",
    "run_deterministic_checks",
    "split_source_entries",
    "guard_copy_pass",
    "narrative_evidence_numbers",
    "evidence_refs_outside_selection",
    "catalog_provenance_numbers",
    "summarize_frame_unit_declarations",
]