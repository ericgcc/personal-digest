"""Machine-readable result records and their persistence.

One record is produced per *historical run x editorial stage*. Records carry the
raw metrics, not judgements: no composite score is invented, and deterministic
changes are preserved as raw deltas rather than being labelled better or worse.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean as _statistics_mean, median as _statistics_median
from typing import Any, Iterable, Mapping, Sequence

from ..historical.run_model import HistoricalRun, StageArtifact
from ..semantic.metric import SemanticResult

#: Deterministic keys for which a raw stage-to-stage delta is recorded.
#: The formula keys are the five cross-language formulas; language-specific
#: formulas stay in ``readability_formulas_json`` only, because a cross-language
#: delta of a language-specific formula would be meaningless.
DELTA_KEYS: tuple[str, ...] = (
    "word_count",
    "sentence_total",
    "sentence_mean_length",
    "sentence_median_length",
    "sentence_p90_length",
    "sentence_max_length",
    "sentence_over_long_ratio",
    "paragraph_total",
    "paragraph_median_length",
    "paragraph_p90_length",
    "readability_avg_words_per_sentence",
    "readability_polysyllable_ratio",
    "acronym_density",
    "identifier_density",
    "parenthetical_density",
    "numeric_token_density",
    # Flat formula keys. The bare formula names never appear in a flattened
    # record, so referencing them here would silently produce no delta.
    "formula_gunning_fog",
    "formula_smog",
    "formula_coleman_liau",
    "formula_ari",
    "formula_lix",
)

#: Formula keys promoted to their own CSV column (the cross-language set).
UNIVERSAL_FORMULA_COLUMNS: tuple[str, ...] = (
    "gunning_fog",
    "smog",
    "coleman_liau",
    "ari",
    "lix",
)

#: Keys that belong to the semantic result rather than the deterministic one.
#: Used to round-trip a flat JSONL record back into its structured form.
SEMANTIC_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "semantic_score",
        "semantic_mode",
        "semantic_summary",
        "semantic_error",
        "semantic_metric_name",
        "semantic_scope",
        "semantic_chars",
        "semantic_words",
        "semantic_source_catalog_removed",
        "semantic_evaluated_at",
        "semantic_section_count",
        "semantic_substantive_section_count",
        "semantic_sections",
        # v3: the absolute assessment, carried by both modes.
        "semantic_overall_score",
        "semantic_weakest_section_id",
        "semantic_weakest_section_score",
        "semantic_critical_failure_count",
        "semantic_sections_understood",
        "semantic_sections_total",
        "semantic_sections_understood_ratio",
        "semantic_issue_counts",
        "semantic_issues",
        "semantic_revision_priorities",
        # v3: the six reader-facing dimensions.
        "dim_first_pass_comprehension",
        "dim_context_sufficiency",
        "dim_explanatory_clarity",
        "dim_synthesis_quality",
        "dim_narrative_coherence",
        "dim_reader_orientation",
        # v3: comparison mode only.
        "regression_status",
        "regression_material",
        "regression_lost_context",
        "regression_lost_explanations",
        "regression_new_ambiguities",
        "regression_broken_connections",
        "regression_improvements",
        "regression_affected_sections",
        "regression_retry_instructions",
        "before_artifact",
        "after_artifact",
        "judge_provider",
        "judge_model",
        "judge_requests",
        "judge_calls",
        "judge_attempts",
        "judge_prompt_tokens",
        "judge_completion_tokens",
        "judge_total_tokens",
        "judge_reasoning_tokens",
        "judge_failures",
        "evaluation_id",
        "evaluation_steps_version",
        "rubric_version",
        "schema_version",
        "preprocessing_version",
        "deepeval_version",
        "readsight_version",
    }
)

_RECORD_META_KEYS: tuple[str, ...] = (
    "run_id",
    "digest_id",
    "digest_style",
    "stage_index",
    "stage_name",
    "stage_kind",
    "editorial_phase",
    "artifact_path",
    "evaluated",
    "evaluation_skipped_reason",
)


@dataclass
class StageMetricRecord:
    """Every raw metric for one run-stage pair, plus its provenance.

    One record exists per historical run x editorial stage. Stages whose declared
    artifact type is not prose (JSON fixtures, rendered HTML) carry
    ``evaluated=False`` and a reason instead of metrics, so the ordering of the
    real pipeline stays visible without treating machine artifacts as prose.
    """

    run_id: str
    digest_id: str | None
    digest_style: str | None
    stage_index: int
    stage_name: str
    stage_kind: str
    editorial_phase: str | None
    artifact_path: str | None
    deterministic: dict[str, Any] = field(default_factory=dict)
    semantic: dict[str, Any] = field(default_factory=dict)
    deltas: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
    evaluated: bool = True
    skip_reason: str | None = None

    @property
    def semantic_score(self) -> float | None:
        value = self.semantic.get("semantic_score")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def has_metrics(self) -> bool:
        return isinstance(self.deterministic.get("word_count"), (int, float))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "digest_id": self.digest_id,
            "digest_style": self.digest_style,
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "stage_kind": self.stage_kind,
            "editorial_phase": self.editorial_phase,
            "artifact_path": self.artifact_path,
            "evaluated": self.evaluated,
            "evaluation_skipped_reason": self.skip_reason,
        }
        for key, value in self.deterministic.items():
            payload[key] = (
                value
                if isinstance(value, (str, int, float, bool)) or value is None
                else json.dumps(value, ensure_ascii=False, sort_keys=True)
            )
        # Promote the cross-language formulas to flat columns for convenience;
        # the full per-language set remains in readability_formulas_json.
        formulas = self.deterministic.get("readability_formulas_json")
        if isinstance(formulas, dict):
            for key in UNIVERSAL_FORMULA_COLUMNS:
                entry = formulas.get(key)
                payload[f"formula_{key}"] = (
                    entry.get("score") if isinstance(entry, dict) else None
                )
        payload.update(self.semantic)
        payload.update({f"delta_{key}": value for key, value in self.deltas.items()})
        payload.update(self.evaluation)
        return payload


def build_record(
    run: HistoricalRun,
    stage: StageArtifact,
    deterministic: Mapping[str, Any],
    *,
    semantic: SemanticResult | None,
    deltas: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    evaluated: bool = True,
    skip_reason: str | None = None,
) -> StageMetricRecord:
    """Assemble one record."""
    semantic_payload: dict[str, Any] = {}
    if semantic is not None:
        semantic_payload = dict(semantic.to_dict())
        # The judge's own verdict is preserved but kept out of the wide CSV.
        semantic_payload.setdefault("semantic_summary", semantic.reason)

    return StageMetricRecord(
        run_id=run.run_id,
        digest_id=run.digest_id,
        digest_style=run.style,
        stage_index=stage.stage_index,
        stage_name=stage.stage_name,
        stage_kind=stage.kind,
        editorial_phase=stage.editorial_phase,
        artifact_path=str(stage.artifact_path) if stage.artifact_path else None,
        deterministic=dict(deterministic),
        semantic=semantic_payload,
        deltas=dict(deltas),
        evaluation=dict(evaluation),
        evaluated=evaluated,
        skip_reason=skip_reason,
    )


def promote_formulas(flat: Mapping[str, Any]) -> dict[str, Any]:
    """Add flat ``formula_<key>`` entries for the cross-language formulas.

    The deterministic metrics carry the full per-language formula record under
    ``readability_formulas_json``. Deltas and CSV columns need the five
    cross-language formulas as scalars, so they are promoted here — before
    deltas are computed — rather than only at serialization time. Without this,
    ``delta_formula_lix`` would silently never be produced.
    """
    promoted = dict(flat)
    formulas = flat.get("readability_formulas_json")
    if isinstance(formulas, dict):
        for key in UNIVERSAL_FORMULA_COLUMNS:
            entry = formulas.get(key)
            if isinstance(entry, dict) and isinstance(entry.get("score"), (int, float)):
                promoted[f"formula_{key}"] = entry["score"]
    return promoted


def compute_deltas(
    current: Mapping[str, Any], previous: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Raw stage-to-stage deltas for the tracked deterministic keys.

    Deltas preserve the raw sign and magnitude. A rising p90 sentence length is
    not labelled "worse" here; interpretation belongs to the reader of the
    report, not to the record.
    """
    if previous is None:
        return {}
    deltas: dict[str, Any] = {}
    for key in DELTA_KEYS:
        left = current.get(key)
        right = previous.get(key)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            deltas[key] = round(float(left) - float(right), 6)
    return deltas


def record_from_flat(row: Mapping[str, Any]) -> StageMetricRecord:
    """Reconstruct a record from its flat JSONL representation.

    This lets the ``report`` command run against previously written results
    without re-evaluating anything.
    """
    meta = {key: row.get(key) for key in _RECORD_META_KEYS}
    deterministic: dict[str, Any] = {}
    semantic: dict[str, Any] = {}
    deltas: dict[str, Any] = {}
    for key, value in row.items():
        if key in _RECORD_META_KEYS:
            continue
        if key.startswith("delta_"):
            deltas[key[len("delta_") :]] = value
        elif key in SEMANTIC_RECORD_KEYS:
            semantic[key] = value
        else:
            deterministic[key] = value

    formulas = deterministic.get("readability_formulas_json")
    if isinstance(formulas, str):
        try:
            deterministic["readability_formulas_json"] = json.loads(formulas)
        except json.JSONDecodeError:
            pass

    return StageMetricRecord(
        run_id=str(meta["run_id"]),
        digest_id=meta.get("digest_id"),
        digest_style=meta.get("digest_style"),
        stage_index=int(meta.get("stage_index") or 0),
        stage_name=str(meta.get("stage_name")),
        stage_kind=str(meta.get("stage_kind") or "unknown"),
        editorial_phase=meta.get("editorial_phase"),
        artifact_path=meta.get("artifact_path"),
        deterministic=deterministic,
        semantic=semantic,
        deltas=deltas,
        evaluation={},
        evaluated=bool(row.get("evaluated", True)),
        skip_reason=row.get("evaluation_skipped_reason"),
    )


def semantic_delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 6)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _column_order(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return a stable column order: first-seen order across all rows."""
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            seen.setdefault(key, None)
    return list(seen)


def write_jsonl(path: Path, records: Iterable[StageMetricRecord]) -> int:
    """Write one JSON object per record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def write_csv(path: Path, records: Sequence[StageMetricRecord], *, drop: Sequence[str] = ()) -> int:
    """Write the same records as CSV, dropping long free-text columns."""
    rows = [record.to_dict() for record in records]
    for row in rows:
        for key in drop:
            row.pop(key, None)
    columns = _column_order(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def _numeric_values(rows: Sequence[Mapping[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _series_mean(values: Sequence[float]) -> float | None:
    return round(float(_statistics_mean(values)), 6) if values else None


def _series_median(values: Sequence[float]) -> float | None:
    return round(float(_statistics_median(values)), 6) if values else None


def _median(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    return _series_median(_numeric_values(rows, key))


#: The six reader-facing dimensions v3 reports instead of one blended score.
DIMENSION_KEYS: tuple[str, ...] = (
    "first_pass_comprehension",
    "context_sufficiency",
    "explanatory_clarity",
    "synthesis_quality",
    "narrative_coherence",
    "reader_orientation",
)


def _mean(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    return _series_mean(_numeric_values(rows, key))


SUMMARY_COLUMNS: tuple[str, ...] = (
    "digest_style",
    "language_code",
    "stage_name",
    "sample_count",
    "semantic_sample_count",
    "semantic_mean",
    "semantic_median",
    "semantic_min",
    "semantic_max",
    "semantic_delta_mean",
    "semantic_delta_median",
    # v3 reader-facing signals. The mean alone cannot show a digest that reads
    # well on average but fails locally, which is the effect v3 exists to expose.
    "semantic_weakest_mean",
    "semantic_critical_failure_total",
    "semantic_critical_failure_documents",
    "semantic_sections_understood_ratio_mean",
    *[f"dim_{key}_mean" for key in DIMENSION_KEYS],
    "readability_median_word_count",
    *[f"formula_{key}_median" for key in UNIVERSAL_FORMULA_COLUMNS],
    "readability_avg_words_per_sentence_median",
    "readability_polysyllable_ratio_median",
    "sentence_mean_length_median",
    "sentence_median_length_median",
    "sentence_p90_length_median",
    "sentence_max_length_median",
    "sentence_over_long_ratio_median",
    "paragraph_median_length_median",
    "paragraph_p90_length_median",
    "acronym_density_median",
    "identifier_density_median",
    "parenthetical_density_median",
    "numeric_token_density_median",
    "heading_count_median",
    "mean_words_per_section_median",
)


def stage_summary_rows(records: Sequence[StageMetricRecord]) -> list[dict[str, Any]]:
    """Aggregate records by digest style, stage and language.

    Grouping by language code is deliberate: readability formulas are not
    equivalent across languages, so no cross-language average is produced.
    """
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        if not record.has_metrics:
            # Non-prose stages carry a skip reason instead of metrics and are
            # excluded from every aggregate.
            continue
        row = record.to_dict()
        key = (
            str(row.get("digest_style")),
            str(row.get("language_code")),
            str(row.get("stage_name")),
        )
        groups.setdefault(key, []).append(row)

    def stage_order(name: str) -> tuple[int, str]:
        for record in records:
            if record.stage_name == name:
                return (record.stage_index, name)
        return (999, name)

    summaries: list[dict[str, Any]] = []
    for (style, language, stage), rows in groups.items():
        scores = _numeric_values(rows, "semantic_score")
        delta_key = "delta_semantic_score"
        summary: dict[str, Any] = {
            "digest_style": style,
            "language_code": language,
            "stage_name": stage,
            "sample_count": len(rows),
            "semantic_sample_count": len(scores),
            "semantic_mean": _series_mean(scores),
            "semantic_median": _series_median(scores),
            "semantic_min": _round(min(scores)) if scores else None,
            "semantic_max": _round(max(scores)) if scores else None,
            "semantic_delta_mean": _mean(rows, delta_key),
            "semantic_delta_median": _median(rows, delta_key),
            "semantic_weakest_mean": _mean(rows, "semantic_weakest_section_score"),
            "semantic_critical_failure_total": sum(
                int(value)
                for value in _numeric_values(rows, "semantic_critical_failure_count")
            ),
            "semantic_critical_failure_documents": sum(
                1
                for row in rows
                if isinstance(row.get("semantic_critical_failure_count"), (int, float))
                and row["semantic_critical_failure_count"] > 0
            ),
            "semantic_sections_understood_ratio_mean": _mean(
                rows, "semantic_sections_understood_ratio"
            ),
            **{
                f"dim_{key}_mean": _mean(rows, f"dim_{key}")
                for key in DIMENSION_KEYS
            },
            "readability_median_word_count": _median(rows, "word_count"),
            "readability_avg_words_per_sentence_median": _median(
                rows, "readability_avg_words_per_sentence"
            ),
            "readability_polysyllable_ratio_median": _median(
                rows, "readability_polysyllable_ratio"
            ),
            "sentence_mean_length_median": _median(rows, "sentence_mean_length"),
            "sentence_median_length_median": _median(rows, "sentence_median_length"),
            "sentence_p90_length_median": _median(rows, "sentence_p90_length"),
            "sentence_max_length_median": _median(rows, "sentence_max_length"),
            "sentence_over_long_ratio_median": _median(rows, "sentence_over_long_ratio"),
            "paragraph_median_length_median": _median(rows, "paragraph_median_length"),
            "paragraph_p90_length_median": _median(rows, "paragraph_p90_length"),
            "acronym_density_median": _median(rows, "acronym_density"),
            "identifier_density_median": _median(rows, "identifier_density"),
            "parenthetical_density_median": _median(rows, "parenthetical_density"),
            "numeric_token_density_median": _median(rows, "numeric_token_density"),
            "heading_count_median": _median(rows, "heading_count"),
            "mean_words_per_section_median": _median(rows, "mean_words_per_section"),
        }
        for key in UNIVERSAL_FORMULA_COLUMNS:
            summary[f"formula_{key}_median"] = _median(rows, f"formula_{key}")
        summaries.append(summary)

    summaries.sort(
        key=lambda item: (item["digest_style"], item["language_code"], stage_order(item["stage_name"]))
    )
    return summaries


def write_stage_summary(path: Path, records: Sequence[StageMetricRecord]) -> int:
    rows = stage_summary_rows(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SUMMARY_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def write_semantic_reasons(path: Path, records: Sequence[StageMetricRecord]) -> int:
    """Persist the structured semantic verdicts, which CSV cannot carry well."""
    payload = [
        {
            "run_id": record.run_id,
            "digest_id": record.digest_id,
            "digest_style": record.digest_style,
            "stage_index": record.stage_index,
            "stage_name": record.stage_name,
            "language_code": record.deterministic.get("language_code"),
            "semantic_score": record.semantic.get("semantic_score"),
            "semantic_delta": record.deltas.get("semantic_score"),
            "semantic_summary": record.semantic.get("semantic_summary"),
            "semantic_weakest_section_id": record.semantic.get("semantic_weakest_section_id"),
            "semantic_weakest_section_score": record.semantic.get(
                "semantic_weakest_section_score"
            ),
            "semantic_critical_failure_count": record.semantic.get(
                "semantic_critical_failure_count"
            ),
            "semantic_sections_understood_ratio": record.semantic.get(
                "semantic_sections_understood_ratio"
            ),
            "semantic_issue_counts": record.semantic.get("semantic_issue_counts"),
            "semantic_issues": record.semantic.get("semantic_issues"),
            "semantic_sections": record.semantic.get("semantic_sections"),
            "semantic_revision_priorities": record.semantic.get(
                "semantic_revision_priorities"
            ),
            "semantic_error": record.semantic.get("semantic_error"),
        }
        for record in records
        if record.semantic
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(payload)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
