"""Deterministic validation of the structured editorial artifacts.

Python port of ``src/editorial/validation/editorial.mjs``.

This module exists because two structured artifacts carry *decisions* the rest of the
pipeline cannot re-derive: ``analysis.json`` carries the selection decisions and the
proposed source relationships, and ``frame.json`` carries the editorial units, the evidence
each unit needs, and the plan's word arithmetic.

Everything here is mechanical. It checks that required fields exist, that vocabularies are
the canonical ones, that declared source numbers exist, and that the numbers add up. It does
**not** judge whether a thread is worth writing or whether a synthesis is illuminating.

Nothing here is style-specific. The thresholds come from the active profile's ``composition``
block, and a profile that enforces nothing produces no findings.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------------------
# Canonical vocabularies
# ---------------------------------------------------------------------------------------

CANONICAL_RELATIONSHIP_TYPES: tuple[str, ...] = (
    "reinforcement",
    "extension",
    "qualification",
    "contradiction",
    "complementarity",
    "shared_cause_or_consequence",
    "independence",
)

CANONICAL_SELECTION_DECISIONS: tuple[str, ...] = ("keep", "split", "demote", "cut")

CANONICAL_EXPLANATION_SHAPES: tuple[str, ...] = (
    "mechanism",
    "contradiction",
    "comparison",
    "causal_chain",
    "consequence",
    "tension",
)

ANALYSIS_CLUSTER_KEYS: tuple[str, ...] = (
    "clusters",
    "candidate_ideas",
    "candidate_clusters",
    "candidate_ideas_and_clusters",
    "candidate_threads",
)

ANALYSIS_GROUPING_FALLBACK_KEYS: tuple[str, ...] = (*ANALYSIS_CLUSTER_KEYS, "cross_source_relationships")

FRAME_MODES: tuple[str, ...] = ("threads", "catalog_only")

WEAK_VALUE_BASES: tuple[str, ...] = (
    "technical_novelty",
    "scale",
    "recency",
    "detail_volume",
    "prominence",
)

UNIT_DISPOSITIONS: tuple[str, ...] = ("keep", "split", "demote", "cut")


# ---------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------


def _is_plain_object(value: Any) -> bool:
    return isinstance(value, Mapping)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and len(value.strip()) > 0


def _source_numbers_of(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    numbers = []
    for item in value:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        numbers.append(number)
    return numbers


def _heading(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text if text is not None else "")).strip()[:90]


def read_word_allocation(value: Any) -> dict[str, Any] | None:
    """Normalize a word allocation that may be an exact number, a ``{min,max}`` object, or a
    range string such as ``"80–130"``.

    The numeric form is what the contracts require, because it is the only form that adds up.
    The other two are accepted so this validator can be pointed at an artifact recorded before
    the numeric form existed, and the encoding actually seen is reported back so a range can
    never be mistaken for an exact allocation.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return {"words": value, "encoding": "number", "min": value, "max": value}
    if _is_plain_object(value):
        try:
            maximum = float(value.get("max"))
        except (TypeError, ValueError):
            return None
        try:
            minimum = float(value.get("min"))
        except (TypeError, ValueError):
            minimum = maximum
        return {"words": maximum, "encoding": "range", "min": minimum, "max": maximum}
    if isinstance(value, str):
        tokens = re.findall(r"\d[\d,]*", value)
        numbers = [int(token.replace(",", "")) for token in tokens]
        if len(numbers) == 1:
            return {"words": numbers[0], "encoding": "range", "min": numbers[0], "max": numbers[0]}
        if len(numbers) >= 2:
            return {"words": max(numbers), "encoding": "range", "min": min(numbers), "max": max(numbers)}
    return None


# ---------------------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------------------


def _finding(*, code: str, severity: str, message: str, unit: str | None = None, details: Any = None) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "severity": severity, "unit": unit, "message": message}
    if details is not None:
        value["details"] = details
    return value


def _summarize(findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    violations = [item for item in findings if item["severity"] == "gate"]
    warnings = [item for item in findings if item["severity"] == "advisory"]
    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "counts": {"gate": len(violations), "advisory": len(warnings)},
    }


def _retained(unit: Any) -> bool:
    """Whether a unit is part of the narrative the draft stage writes.

    Only ``keep`` units are. ``split`` means the unit was replaced by others, and ``demote``
    and ``cut`` mean it was set aside — so the narrative constraints apply to retained units
    and to nothing else.
    """
    disposition = unit.get("disposition", "keep") if _is_plain_object(unit) else "keep"
    return disposition == "keep"


# ---------------------------------------------------------------------------------------
# Frame validation
# ---------------------------------------------------------------------------------------


def _validate_unit(
    *,
    unit: Any,
    index: int,
    constraints: Mapping[str, Any],
    enforced: Sequence[str],
    source_numbers: set[int],
    findings: list[dict[str, Any]],
    retained: bool,
) -> dict[str, Any] | None:
    if _non_empty_string(unit.get("unit_id") if _is_plain_object(unit) else None):
        unit_id = unit["unit_id"]
    elif _is_plain_object(unit) and _non_empty_string(unit.get("id")):
        unit_id = unit["id"]
    else:
        unit_id = f"#{index + 1}"
    label = f'{unit_id} "{_heading(unit.get("working_title") if _is_plain_object(unit) else None)}"'

    if not _is_plain_object(unit):
        findings.append(
            _finding(code="unit:shape", severity="gate", unit=unit_id, message=f"editorial unit {unit_id} is not an object")
        )
        return None

    declared = _source_numbers_of(unit.get("selected_source_numbers"))

    # --- disposition -------------------------------------------------------------------
    disposition = unit.get("disposition", "keep")
    if disposition not in UNIT_DISPOSITIONS:
        findings.append(
            _finding(
                code="unit:unknown-disposition",
                severity="gate",
                unit=unit_id,
                message=f"{label} declares disposition {_js(unit.get('disposition'))}; the vocabulary is {', '.join(UNIT_DISPOSITIONS)}",
                details={"disposition": unit.get("disposition"), "allowed": list(UNIT_DISPOSITIONS)},
            )
        )

    # --- source existence -------------------------------------------------------------
    if "sources_per_unit.exists" in enforced:
        unknown = [number for number in declared if number not in source_numbers]
        if unknown:
            findings.append(
                _finding(
                    code="unit:unknown-source",
                    severity="gate",
                    unit=unit_id,
                    message=f"{label} declares source number(s) that do not exist in the corpus: {', '.join(map(str, unknown))}",
                    details={"unknown": unknown},
                )
            )

    if not retained:
        refs = unit.get("evidence_refs") if isinstance(unit.get("evidence_refs"), list) else []
        return {
            "id": unit_id,
            "declared": declared,
            "retained": False,
            "disposition": disposition,
            "words": None,
            "allocation": None,
            "spine": [],
            "shape": None,
            "refs": refs,
        }

    # --- source count ------------------------------------------------------------------
    per_unit = constraints.get("sources_per_unit") or {}
    if "sources_per_unit.min" in enforced and isinstance(per_unit.get("min"), int) and len(declared) < per_unit["min"]:
        findings.append(
            _finding(
                code="unit:too-few-sources",
                severity="gate",
                unit=unit_id,
                message=f"{label} declares {len(declared)} source(s); this style requires at least {per_unit['min']} to explain a concrete subject through more than one source",
                details={"declared": declared, "min": per_unit["min"]},
            )
        )
    if "sources_per_unit.max" in enforced and isinstance(per_unit.get("max"), int) and len(declared) > per_unit["max"]:
        findings.append(
            _finding(
                code="unit:too-many-sources",
                severity="gate",
                unit=unit_id,
                message=(
                    f"{label} declares {len(declared)} sources; this style permits at most {per_unit['max']}. "
                    "Split it only if the resulting threads are independently coherent, otherwise demote the least essential material to the source catalog."
                ),
                details={"declared": declared, "max": per_unit["max"]},
            )
        )

    # --- distinct, explainable role ----------------------------------------------------
    role_refs: dict[int, Any] = {}
    if "unit:source_roles" in enforced:
        refs = unit.get("evidence_refs") if isinstance(unit.get("evidence_refs"), list) else []
        by_number: dict[int, Any] = {}
        for ref in refs:
            if not _is_plain_object(ref):
                continue
            try:
                number = int(ref.get("source_number"))
            except (TypeError, ValueError):
                continue
            by_number[number] = ref
        role_refs = by_number
        missing = [number for number in declared if number not in by_number]
        if missing:
            findings.append(
                _finding(
                    code="unit:missing-role",
                    severity="gate",
                    unit=unit_id,
                    message=(
                        f"{label} selects source(s) {', '.join(map(str, missing))} with no `evidence_refs` entry. "
                        "A selected source that states no role has no declared reason to occupy space."
                    ),
                    details={"missing": missing},
                )
            )
        empty_roles = [
            number for number in declared if number in by_number and not _non_empty_string(by_number[number].get("role"))
        ]
        if empty_roles:
            findings.append(
                _finding(
                    code="unit:empty-role",
                    severity="gate",
                    unit=unit_id,
                    message=f"{label} gives source(s) {', '.join(map(str, empty_roles))} an empty role",
                    details={"emptyRoles": empty_roles},
                )
            )
        outside_selection = [number for number in by_number if number not in declared]
        if outside_selection:
            findings.append(
                _finding(
                    code="unit:roles-outside-selection",
                    severity="gate",
                    unit=unit_id,
                    message=(
                        f"{label} has `evidence_refs` for source(s) {', '.join(map(str, outside_selection))} that are not in `selected_source_numbers`. "
                        "The writer receives only the declared selection, so a role describing anything else refers to evidence it will not have."
                    ),
                    details={"outsideSelection": outside_selection, "declared": declared},
                )
            )
        seen: dict[str, int] = {}
        for number in declared:
            role = by_number.get(number, {}).get("role") if number in by_number else None
            if not _non_empty_string(role):
                continue
            key = _heading(role).lower()
            if key in seen:
                findings.append(
                    _finding(
                        code="unit:duplicate-role",
                        severity="advisory",
                        unit=unit_id,
                        message=(
                            f'{label} gives sources {seen[key]} and {number} the identical role "{_heading(role)}". '
                            "Each source should have an explainable role of its own."
                        ),
                        details={"sources": [seen[key], number], "role": _heading(role)},
                    )
                )
            else:
                seen[key] = number

    # --- progression -------------------------------------------------------------------
    if "unit:progression" in enforced:
        spine = [item for item in (unit.get("narrative_spine") or []) if _non_empty_string(item)] if isinstance(unit.get("narrative_spine"), list) else []
        if len(spine) < 2:
            findings.append(
                _finding(
                    code="unit:no-progression",
                    severity="gate",
                    unit=unit_id,
                    message=(
                        f"{label} has {len(spine)} narrative_spine move(s). A thread must progress from orientation through evidence to the relationship or implication, which needs at least two ordered moves."
                    ),
                    details={"spine": spine},
                )
            )
        else:
            shape = unit.get("explanation_shape")
            if "unit:explanation_shape" in enforced and shape not in CANONICAL_EXPLANATION_SHAPES:
                findings.append(
                    _finding(
                        code="unit:unknown-explanation-shape",
                        severity="gate",
                        unit=unit_id,
                        message=f"{label} declares explanation_shape {_js(shape)}; the canonical shapes are {', '.join(CANONICAL_EXPLANATION_SHAPES)}",
                        details={"shape": shape, "allowed": list(CANONICAL_EXPLANATION_SHAPES)},
                    )
                )

    # --- the allocation must be able to explain the evidence ---------------------------
    allocation = read_word_allocation(unit.get("depth_target_words"))
    if allocation is None:
        if "unit:budget_present" in enforced:
            findings.append(
                _finding(
                    code="unit:no-allocation",
                    severity="gate",
                    unit=unit_id,
                    message=f"{label} has no readable `depth_target_words`",
                )
            )
        return None
    if "unit:evidence_fits_budget" in enforced and len(declared) > 0:
        per_source = allocation["words"] / len(declared)
        floor = constraints.get("min_words_per_source")
        comfortable = constraints.get("comfortable_words_per_source")
        if isinstance(floor, (int, float)) and per_source < floor:
            findings.append(
                _finding(
                    code="unit:evidence-exceeds-budget",
                    severity="gate",
                    unit=unit_id,
                    message=(
                        f"{label} allocates {_num(allocation['words'])} words to {len(declared)} sources — {per_source:.1f} words per source, "
                        f"below the {floor}-word floor at which a source's contribution can be stated rather than named. "
                        "Reduce the source count, split the thread, or move the least essential material to the source catalog."
                    ),
                    details={"words": allocation["words"], "sources": len(declared), "per_source": round(per_source, 1), "floor": floor},
                )
            )
        elif isinstance(comfortable, (int, float)) and per_source < comfortable:
            findings.append(
                _finding(
                    code="unit:thin-evidence-budget",
                    severity="advisory",
                    unit=unit_id,
                    message=(
                        f"{label} allocates {per_source:.1f} words per source, below the {comfortable}-word comfort band. "
                        "The thread can state each source's contribution but has little room to explain the relationship between them."
                    ),
                    details={"words": allocation["words"], "sources": len(declared), "per_source": round(per_source, 1), "comfortable": comfortable},
                )
            )

    if allocation["encoding"] != "number":
        findings.append(
            _finding(
                code="unit:allocation-is-a-range",
                severity="gate" if "arithmetic" in enforced else "advisory",
                unit=unit_id,
                message=f"{label} gives `depth_target_words` as a range ({_js(unit.get('depth_target_words'))}); an exact number is required so the edition's arithmetic can be checked",
            )
        )

    return {
        "id": unit_id,
        "declared": declared,
        "retained": True,
        "disposition": disposition,
        "words": allocation["words"],
        "allocation": allocation,
        "spine": unit.get("narrative_spine") or [],
        "shape": unit.get("explanation_shape"),
        "refs": role_refs,
    }


def validate_frame(*, frame: Any, corpus: Any, profile: Any) -> dict[str, Any]:
    """Validate a frame against the active profile's composition constraints.

    Pure: it reads the frame, the corpus's source numbers and the profile's declared
    constraints, and returns findings. No I/O, so it can be run over a recorded artifact from
    a historical run with no model call.
    """
    findings: list[dict[str, Any]] = []
    constraints = (profile.composition if profile else None) or {}
    enforced = constraints.get("enforced") if isinstance(constraints.get("enforced"), list) else []
    budget = profile.budget if profile else None
    sources = corpus.get("sources") if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list) else []
    source_numbers = set()
    for source in sources:
        try:
            number = int(source.get("source_number"))
        except (TypeError, ValueError, AttributeError):
            continue
        source_numbers.add(number)

    if not _is_plain_object(frame):
        findings.append(_finding(code="frame:shape", severity="gate", message="frame is not an object"))
        return {**_summarize(findings), "summary": None}

    # --- edition mode ------------------------------------------------------------------
    mode = frame.get("mode") if frame.get("mode") in FRAME_MODES else "threads"
    mode_declared = frame.get("mode") in FRAME_MODES
    if not mode_declared and "edition_mode" in enforced:
        findings.append(
            _finding(
                code="frame:no-edition-mode",
                severity="gate",
                message=(
                    f"the frame declares no `mode`; this style requires one of {', '.join(FRAME_MODES)} "
                    "so that a deliberately sparse catalog-only edition is distinguishable from a plan that failed to find threads"
                ),
                details={"allowed": list(FRAME_MODES)},
            )
        )

    units = frame.get("editorial_units") if isinstance(frame.get("editorial_units"), list) else []
    retained = [unit for unit in units if _is_plain_object(unit) and (unit.get("disposition", "keep")) == "keep"]

    # --- thread count ------------------------------------------------------------------
    unit_count = constraints.get("unit_count") or {}
    if mode == "catalog_only":
        if len(retained) > 0:
            findings.append(
                _finding(
                    code="frame:catalog-only-has-threads",
                    severity="gate",
                    message=(
                        f'the frame declares mode "catalog_only" but retains {len(retained)} editorial unit(s). '
                        "A catalog-only edition is the honest outcome when no cross-source thread qualifies; it is not a label for a normal edition."
                    ),
                    details={"retained": [unit.get("unit_id", unit.get("id")) for unit in retained]},
                )
            )
    else:
        if "unit_count.min" in enforced and isinstance(unit_count.get("min"), int) and len(retained) < unit_count["min"]:
            findings.append(
                _finding(
                    code="frame:too-few-threads",
                    severity="gate",
                    message=(
                        f"the frame retains {len(retained)} editorial unit(s); this style requires {unit_count['min']}–{unit_count.get('max') or 'any'} "
                        'when any cross-source thread qualifies. If none qualifies, declare mode "catalog_only" instead of planning none.'
                    ),
                    details={"retained": len(retained), "min": unit_count["min"]},
                )
            )
        if "unit_count.max" in enforced and isinstance(unit_count.get("max"), int) and len(retained) > unit_count["max"]:
            findings.append(
                _finding(
                    code="frame:too-many-threads",
                    severity="gate",
                    message=(
                        f"the frame retains {len(retained)} editorial units; this style permits at most {unit_count['max']}. "
                        "Demote or cut the least essential thread rather than compressing them all."
                    ),
                    details={"retained": len(retained), "max": unit_count["max"]},
                )
            )

    # --- per unit ----------------------------------------------------------------------
    validated: list[dict[str, Any]] = []
    for index, unit in enumerate(units):
        result = _validate_unit(
            unit=unit,
            index=index,
            constraints=constraints,
            enforced=enforced,
            source_numbers=source_numbers,
            findings=findings,
            retained=_is_plain_object(unit) and _retained(unit),
        )
        if result is not None:
            validated.append(result)

    if "unit:explanation_shape" in enforced:
        shapes = [
            item["shape"]
            for item in validated
            if item["retained"] and item["shape"] in CANONICAL_EXPLANATION_SHAPES
        ]
        if len(shapes) > 1 and len(set(shapes)) == 1:
            findings.append(
                _finding(
                    code="frame:single-explanation-shape",
                    severity="advisory",
                    message=f'all {len(shapes)} retained threads use the "{shapes[0]}" shape. Threads should not share one rhetorical template.',
                    details={"shape": shapes[0], "threads": len(shapes)},
                )
            )

    # --- arithmetic --------------------------------------------------------------------
    pattern = frame.get("budget")
    arithmetic = None
    if not _is_plain_object(pattern):
        if "unit:budget_present" in enforced:
            findings.append(
                _finding(
                    code="frame:no-budget-block",
                    severity="gate",
                    message="the frame carries no `budget` block, so the plan's arithmetic cannot be checked",
                )
            )
    else:
        arithmetic = _validate_budget_arithmetic(
            frame=frame,
            pattern=pattern,
            validated=validated,
            retained=retained,
            constraints=constraints,
            budget=budget,
            enforced=enforced,
            findings=findings,
            mode=mode,
        )

    result = _summarize(findings)
    return {
        **result,
        "mode": mode,
        "mode_declared": mode_declared,
        "retained_units": len(retained),
        "arithmetic": arithmetic,
    }


def _validate_budget_arithmetic(
    *,
    frame: Any,
    pattern: Mapping[str, Any],
    validated: Sequence[Mapping[str, Any]],
    retained: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any],
    budget: Mapping[str, Any] | None,
    enforced: Sequence[str],
    findings: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    arithmetic_enforced = "arithmetic" in enforced
    catalog_only = mode == "catalog_only"
    opening = read_word_allocation(pattern.get("big_picture_words", pattern.get("big_picture_target_words")))
    targets = pattern.get("unit_depth_targets") if _is_plain_object(pattern.get("unit_depth_targets")) else None

    if opening is None:
        if arithmetic_enforced and not catalog_only:
            findings.append(
                _finding(
                    code="budget:no-opening-allocation",
                    severity="gate",
                    message="the frame's budget declares no readable The Big Picture allocation",
                )
            )
    else:
        if opening["encoding"] != "number":
            findings.append(
                _finding(
                    code="budget:opening-is-a-range",
                    severity="gate" if arithmetic_enforced else "advisory",
                    message=f"{_js(pattern.get('big_picture_words', pattern.get('big_picture_target_words')))} is a range; an exact number is required for the edition's arithmetic to be checkable",
                )
            )
        opening_band = constraints.get("opening_words")
        if "opening_words" in enforced and opening_band and not catalog_only:
            if opening["words"] < opening_band["min"] or opening["words"] > opening_band["max"]:
                findings.append(
                    _finding(
                        code="budget:opening-out-of-band",
                        severity="gate",
                        message=f"The Big Picture is allocated {_num(opening['words'])} words, outside the style's {opening_band['min']}–{opening_band['max']} band",
                        details={"words": opening["words"], "band": opening_band},
                    )
                )

    if not arithmetic_enforced:
        return {
            "enforced": False,
            "opening_words": opening["words"] if opening else None,
            "unit_words": None,
            "total_body_words": None,
            "retained_threads": len(retained),
        }

    if targets is None:
        findings.append(
            _finding(
                code="budget:no-unit-targets",
                severity="gate",
                message="the frame's budget declares no `unit_depth_targets`, so the per-thread allocation cannot be checked",
            )
        )
        return {
            "enforced": True,
            "opening_words": opening["words"] if opening else None,
            "unit_words": None,
            "total_body_words": None,
            "retained_threads": len(retained),
        }

    target_values = []
    for value in targets.values():
        allocation = read_word_allocation(value)
        target_values.append(allocation["words"] if allocation else 0)
    declared_total = sum(target_values)

    retained_ids = _retained_ids_of(retained)
    missing = [item["id"] for item in validated if item["retained"] and item["id"] not in targets]
    extra = [key for key in targets if key not in retained_ids]
    if missing:
        findings.append(
            _finding(
                code="budget:missing-unit-target",
                severity="gate",
                message=f"`unit_depth_targets` omits retained thread(s): {', '.join(missing)}",
                details={"missing": missing},
            )
        )
    if extra:
        findings.append(
            _finding(
                code="budget:orphan-unit-target",
                severity="gate",
                message=f"`unit_depth_targets` names unit(s) that are not retained: {', '.join(extra)}",
                details={"extra": extra},
            )
        )
    mismatched = []
    for item in validated:
        if not item["retained"] or item["id"] not in targets:
            continue
        table = read_word_allocation(targets[item["id"]])
        table_words = table["words"] if table else 0
        if item["words"] != table_words:
            mismatched.append({"id": item["id"], "unit": item["words"], "table": table_words})
    if mismatched:
        findings.append(
            _finding(
                code="budget:unit-target-disagrees",
                severity="gate",
                message="the per-unit allocation and `unit_depth_targets` disagree for: "
                + ", ".join(f"{item['id']} ({_num(item['unit'])} vs {_num(item['table'])})" for item in mismatched),
                details={"mismatched": mismatched},
            )
        )

    total_body = (opening["words"] if opening else 0) + declared_total
    total_unit_field = read_word_allocation(pattern.get("total_unit_words"))
    declared_total_field = total_unit_field["words"] if total_unit_field else None
    body_field = read_word_allocation(
        pattern.get("total_body_words", pattern.get("estimated_body_words_including_big_picture"))
    )
    declared_body_field = body_field["words"] if body_field else None

    if declared_total_field is not None and declared_total_field != declared_total:
        findings.append(
            _finding(
                code="budget:total-unit-words-disagrees",
                severity="gate",
                message=f"`total_unit_words` says {_num(declared_total_field)} but the per-unit allocations sum to {_num(declared_total)}",
                details={"declared": declared_total_field, "computed": declared_total},
            )
        )
    if declared_body_field is not None and declared_body_field != total_body:
        findings.append(
            _finding(
                code="budget:total-body-words-disagrees",
                severity="gate",
                message=(
                    f"the frame states a total body of {_num(declared_body_field)} words; The Big Picture plus the threads sum to {_num(total_body)}. "
                    "An internally inconsistent plan does not say how long the digest is meant to be."
                ),
                details={"declared": declared_body_field, "computed": total_body},
            )
        )

    reserve = (
        round(budget["max"] * constraints["budget_headroom_ratio"])
        if budget and isinstance(constraints.get("budget_headroom_ratio"), (int, float))
        else 0
    )
    if not catalog_only and budget:
        if total_body > budget["max"]:
            findings.append(
                _finding(
                    code="budget:exceeds-maximum",
                    severity="gate",
                    message=(
                        f"the planned body is {_num(total_body)} words ({_num(opening['words'] if opening else 0)} opening + {_num(declared_total)} across {len(retained)} thread(s)), "
                        f"above the style's {budget['min']}–{budget['max']} maximum. An over-budget plan must not be passed to the draft stage: "
                        "demote or cut the least essential thread, or move supporting branches to the source catalog."
                    ),
                    details={"planned": total_body, "opening": opening["words"] if opening else 0, "units": declared_total, "max": budget["max"]},
                )
            )
        elif reserve > 0 and total_body > budget["max"] - reserve:
            findings.append(
                _finding(
                    code="budget:no-headroom",
                    severity="gate",
                    message=(
                        f"the planned body is {_num(total_body)} words against a {budget['max']}-word maximum, leaving {_num(budget['max'] - total_body)} words of editing headroom; "
                        f"this style reserves {reserve}. Reduce the plan so the writing stages have room to explain."
                    ),
                    details={"planned": total_body, "max": budget["max"], "headroom": budget["max"] - total_body, "reserve": reserve},
                )
            )
        if total_body > 0 and total_body < budget["min"]:
            findings.append(
                _finding(
                    code="budget:below-minimum",
                    severity="advisory",
                    message=(
                        f"the planned body is {_num(total_body)} words, below the style's {budget['min']}-word expectation. "
                        "This is only appropriate when the corpus genuinely cannot support more."
                    ),
                    details={"planned": total_body, "min": budget["min"]},
                )
            )

    return {
        "enforced": True,
        "opening_words": opening["words"] if opening else None,
        "opening_encoding": opening["encoding"] if opening else None,
        "unit_words": declared_total,
        "total_body_words": total_body,
        "retained_threads": len(retained),
        "words_per_source_by_thread": {
            item["id"]: (round(item["words"] / len(item["declared"]), 1) if item["declared"] else None)
            for item in validated
            if item["retained"]
        },
        "within_maximum": (total_body <= budget["max"]) if budget else None,
        "style_budget": {"min": budget["min"], "max": budget["max"]} if budget else None,
    }


def _retained_ids_of(retained: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        (unit["unit_id"] if _non_empty_string(unit.get("unit_id")) else unit.get("id"))
        for unit in retained
    }


# ---------------------------------------------------------------------------------------
# Analysis selection validation
# ---------------------------------------------------------------------------------------

ANALYSIS_STRUCTURAL_CODES: tuple[str, ...] = (
    "analysis:shape",
    "analysis:no-cluster-array",
    "analysis:ambiguous-cluster-container",
    "cluster:shape",
    "cluster:missing-fields",
    "cluster:unknown-relationship",
    "cluster:unknown-decision",
    "cluster:no-source-contributions",
    "cluster:contributions-incomplete",
    "cluster:empty-contribution",
)

ANALYSIS_EDITORIAL_CODES: tuple[str, ...] = (
    "analysis:no-alternatives-record",
    "analysis:empty-alternatives-record",
    "analysis:unexpected-cluster-key",
    "cluster:no-exclusions",
    "cluster:empty-value-basis",
)


def validate_analysis_selection(*, analysis: Any, profile: Any) -> dict[str, Any]:
    """Validate the structured selection decisions in ``analysis.json``.

    **Structural** findings are artifact defects: fixable when named, and Frame and the
    selection audit cannot work without them, so they warrant the one correction attempt.
    **Editorial** findings are judgements about the selection, and asking for another model
    call will not settle them. They are recorded for review.

    Neither kind fails the stage.
    """
    findings: list[dict[str, Any]] = []
    constraints = (profile.composition if profile else None) or {}
    enforced = constraints.get("enforced") if isinstance(constraints.get("enforced"), list) else []
    if "analysis_clusters" not in enforced:
        return {**_summarize(findings), "clusters": 0, "considered": 0, "skipped": True}

    if not _is_plain_object(analysis):
        findings.append(_finding(code="analysis:shape", severity="gate", message="analysis is not an object"))
        return {**_summarize(findings), "clusters": 0, "considered": 0}

    answered = [key for key in ANALYSIS_CLUSTER_KEYS if isinstance(analysis.get(key), list)]
    populated = [key for key in answered if len(analysis[key]) > 0]
    cluster_key = (populated[0] if populated else None) or (answered[0] if answered else None)
    if cluster_key is None:
        keys = list(analysis.keys())
        findings.append(
            _finding(
                code="analysis:no-cluster-array",
                severity="gate",
                message=(
                    "the analysis carries no proposed groupings under any known key, so nothing about its selection could be checked. "
                    f"Expected one of: {', '.join(ANALYSIS_CLUSTER_KEYS)}. "
                    + (f"The document's top-level keys are: {', '.join(keys)}." if keys else "The document is empty.")
                ),
                details={"expected": list(ANALYSIS_CLUSTER_KEYS), "present": keys},
            )
        )
        return {**_summarize(findings), "clusters": 0, "considered": 0, "cluster_key": None}

    if len(populated) > 1:
        findings.append(
            _finding(
                code="analysis:ambiguous-cluster-container",
                severity="gate",
                message=(
                    f"the analysis states its groupings in {len(populated)} arrays ({', '.join(populated)}); "
                    f"keep only `{ANALYSIS_CLUSTER_KEYS[0]}`. Duplicated containers can disagree, and a reader that picks one "
                    "cannot know it has the authoritative selection."
                ),
                details={"present": populated, "counts": {key: len(analysis[key]) for key in populated}},
            )
        )

    if len(populated) <= 1 and cluster_key != ANALYSIS_CLUSTER_KEYS[0]:
        findings.append(
            _finding(
                code="analysis:unexpected-cluster-key",
                severity="advisory",
                message=(
                    f"the analysis holds its groupings under `{cluster_key}`; the contract names `{ANALYSIS_CLUSTER_KEYS[0]}`. "
                    "It was read, so the artifact is usable. This is a defect in the instruction rather than in the artifact: "
                    "the array must not be renamed in place, because a second copy under the contract name would leave the "
                    "analysis stating its selection twice. Correct it in the prompt and re-run."
                ),
                details={"found": cluster_key, "expected": ANALYSIS_CLUSTER_KEYS[0], "remedy": "prompt"},
            )
        )

    clusters = analysis[cluster_key]
    seen_decisions: dict[str, int] = {}
    for index, cluster in enumerate(clusters):
        if _is_plain_object(cluster):
            cluster_id = cluster.get("cluster_id", cluster.get("id", f"#{index + 1}"))
        else:
            cluster_id = f"#{index + 1}"
        if not _is_plain_object(cluster):
            findings.append(
                _finding(code="cluster:shape", severity="gate", unit=cluster_id, message=f"cluster {cluster_id} is not an object")
            )
            continue
        label = f'cluster {cluster_id} "{_heading(cluster.get("concrete_subject", cluster.get("title_direction")))}"'
        numbers = _source_numbers_of(cluster.get("source_numbers"))

        missing = []
        if not _non_empty_string(cluster.get("concrete_subject")):
            missing.append("concrete_subject")
        if not _non_empty_string(cluster.get("reader_question")):
            missing.append("reader_question")
        if not numbers:
            missing.append("source_numbers")
        if not _non_empty_string(cluster.get("new_understanding")):
            missing.append("new_understanding")
        if not _non_empty_string(cluster.get("relationship_counter_test", cluster.get("counter_test"))):
            missing.append("relationship_counter_test")
        if not _non_empty_string(cluster.get("selection_reason", cluster.get("why"))):
            missing.append("selection_reason")
        if not _non_empty_string(cluster.get("reader_value_reason")):
            missing.append("reader_value_reason")
        if missing:
            findings.append(
                _finding(
                    code="cluster:missing-fields",
                    severity="gate",
                    unit=cluster_id,
                    message=f"{label} is missing required field(s): {', '.join(missing)}",
                    details={"missing": missing},
                )
            )

        relationship = cluster.get("relationship_type")
        if relationship not in CANONICAL_RELATIONSHIP_TYPES:
            findings.append(
                _finding(
                    code="cluster:unknown-relationship",
                    severity="gate",
                    unit=cluster_id,
                    message=(
                        f"{label} declares relationship_type {_js(relationship)}; "
                        f"the canonical vocabulary is {', '.join(CANONICAL_RELATIONSHIP_TYPES)}. "
                        'Do not compose new labels: a composite such as "extension_plus_qualification" is two relationships, and the thread cannot be tested against either.'
                    ),
                    details={"relationship": relationship, "allowed": list(CANONICAL_RELATIONSHIP_TYPES)},
                )
            )

        decision = cluster.get("selection_decision", cluster.get("decision"))
        if decision not in CANONICAL_SELECTION_DECISIONS:
            findings.append(
                _finding(
                    code="cluster:unknown-decision",
                    severity="gate",
                    unit=cluster_id,
                    message=f"{label} declares selection_decision {_js(decision)}; the vocabulary is {', '.join(CANONICAL_SELECTION_DECISIONS)}",
                    details={"decision": decision, "allowed": list(CANONICAL_SELECTION_DECISIONS)},
                )
            )
        else:
            seen_decisions[decision] = seen_decisions.get(decision, 0) + 1

        if numbers and not isinstance(cluster.get("source_contributions"), list):
            findings.append(
                _finding(
                    code="cluster:no-source-contributions",
                    severity="gate",
                    unit=cluster_id,
                    message=f"{label} states no `source_contributions`; the thread cannot be justified source by source without them",
                )
            )
        elif isinstance(cluster.get("source_contributions"), list):
            covered = set()
            for entry in cluster["source_contributions"]:
                if not _is_plain_object(entry):
                    continue
                try:
                    covered.add(int(entry.get("source_number")))
                except (TypeError, ValueError):
                    continue
            uncovered = [number for number in numbers if number not in covered]
            if uncovered:
                findings.append(
                    _finding(
                        code="cluster:contributions-incomplete",
                        severity="gate",
                        unit=cluster_id,
                        message=f"{label} names source(s) {', '.join(map(str, uncovered))} in `source_numbers` but not in `source_contributions`",
                        details={"uncovered": uncovered},
                    )
                )
            empty = []
            for entry in cluster["source_contributions"]:
                if _is_plain_object(entry) and not _non_empty_string(entry.get("unique_contribution")):
                    try:
                        empty.append(int(entry.get("source_number")))
                    except (TypeError, ValueError):
                        continue
            if empty:
                findings.append(
                    _finding(
                        code="cluster:empty-contribution",
                        severity="gate",
                        unit=cluster_id,
                        message=f"{label} gives source(s) {', '.join(map(str, empty))} an empty unique_contribution",
                        details={"empty": empty},
                    )
                )

        if not isinstance(cluster.get("material_to_exclude", cluster.get("branches_to_cut")), list):
            findings.append(
                _finding(
                    code="cluster:no-exclusions",
                    severity="advisory",
                    unit=cluster_id,
                    message=f"{label} records no `material_to_exclude`. Even when nothing is cut, the decision to keep everything should be deliberate.",
                )
            )

        if cluster.get("value_basis") is not None and not _non_empty_string(cluster.get("value_basis")):
            findings.append(
                _finding(
                    code="cluster:empty-value-basis",
                    severity="advisory",
                    unit=cluster_id,
                    message=f"{label} declares an empty `value_basis`",
                )
            )

    considered = analysis.get("alternatives_considered") if isinstance(analysis.get("alternatives_considered"), list) else None
    if considered is None:
        findings.append(
            _finding(
                code="analysis:no-alternatives-record",
                severity="advisory",
                message=(
                    "the analysis records no `alternatives_considered`. A demoted candidate that simply does not appear is indistinguishable "
                    "from one that was never examined."
                ),
            )
        )
    elif len(considered) == 0 and len(clusters) > 0:
        findings.append(
            _finding(
                code="analysis:empty-alternatives-record",
                severity="advisory",
                message="`alternatives_considered` is empty although the analysis proposes clusters; record what was weighed and dropped.",
            )
        )

    summary = _summarize(findings)
    return {
        **summary,
        "clusters": len(clusters),
        "considered": len(considered) if considered is not None else 0,
        "cluster_key": cluster_key,
        "decisions": dict(seen_decisions),
    }


# ---------------------------------------------------------------------------------------
# Validation feedback
# ---------------------------------------------------------------------------------------

#: Findings whose remedy is a change to the *instructions* rather than to the artifact, and
#: which therefore must not be sent to the model at all.
FEEDBACK_EXCLUDED_CODES: tuple[str, ...] = ("analysis:unexpected-cluster-key",)


def format_validation_feedback(*, stage_name: str, result: Mapping[str, Any]) -> str:
    """Format findings as the feedback a retried attempt receives.

    The retry is only worth its cost if the model is told precisely which unit and which
    number is wrong, so the message carries the violation text verbatim.
    """
    violations = [item for item in result.get("violations", []) if item["code"] not in FEEDBACK_EXCLUDED_CODES]
    warnings = [item for item in result.get("warnings", []) if item["code"] not in FEEDBACK_EXCLUDED_CODES]
    lines = [
        f"VALIDATION FAILED for the {stage_name} artifact you just returned.",
        "",
        "The artifact parses as JSON but violates the style's constraints. Fix exactly these problems",
        "and return the complete corrected artifact. Do not explain the fixes; return the JSON only.",
        "",
    ]
    for item in violations:
        unit = f" ({item['unit']})" if item.get("unit") else ""
        lines.append(f"* [{item['code']}]{unit} {item['message']}")
    if warnings:
        lines.append("")
        lines.append("Also recorded, and worth correcting if the fix is free:")
        for item in warnings:
            unit = f" ({item['unit']})" if item.get("unit") else ""
            lines.append(f"  - [{item['code']}]{unit} {item['message']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------
# JSON-compatible formatting helpers
# ---------------------------------------------------------------------------------------


def _js(value: Any) -> str:
    """Render a value the way ``JSON.stringify`` would, for message parity."""
    import json

    return json.dumps(value, ensure_ascii=False)


def _num(value: Any) -> str:
    """Render a number the way JavaScript's string coercion would.

    ``200.0`` in Python is ``200`` in JavaScript, and the messages are compared verbatim
    against the frozen reference.
    """
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


__all__ = [
    "CANONICAL_RELATIONSHIP_TYPES",
    "CANONICAL_SELECTION_DECISIONS",
    "CANONICAL_EXPLANATION_SHAPES",
    "ANALYSIS_CLUSTER_KEYS",
    "ANALYSIS_GROUPING_FALLBACK_KEYS",
    "FRAME_MODES",
    "WEAK_VALUE_BASES",
    "ANALYSIS_STRUCTURAL_CODES",
    "ANALYSIS_EDITORIAL_CODES",
    "FEEDBACK_EXCLUDED_CODES",
    "read_word_allocation",
    "validate_frame",
    "validate_analysis_selection",
    "format_validation_feedback",
]