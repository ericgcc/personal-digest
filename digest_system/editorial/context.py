"""The run context: the run-owned state a stage reads and writes.

Python port of the context object the JavaScript orchestrator built inline. It is a plain
dataclass rather than a Pydantic model: it is an internal object, not a validated external
boundary, and the migration plan is explicit that a model class is not introduced for every
internal dictionary.

Unlike the JavaScript runner, the context carries absolute paths and never changes the
process's working directory. That removes a hidden global dependency and makes testing and
concurrent execution safer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..config.profiles import StyleProfile
from ..config.reading_instructions import ReadingInstructions, empty_instructions
from ..runtime.artifacts import ROOT, relative_to_root
from .rendering.values import resolve_rendering_values


@dataclass
class Artifact:
    """One stage's produced artifact, as the context holds it."""

    path: Path
    text: str
    json: Any = None
    provenance: str = "runner"
    degraded: bool = False


@dataclass
class RunContext:
    """Everything a stage needs that is owned by the run rather than by the stage."""

    run_id: str
    digest_id: str
    config_path: Path
    style: str
    language: str
    source_path: Path
    timeout_seconds: float
    run_key: str
    run_key_source: str
    digest_name: str | None
    profile: StyleProfile
    style_profile_id: str
    style_profile_source: str
    style_headings: list[str]
    corpus: Mapping[str, Any]
    style_text: str
    #: The digest's parsed reading instructions. Defaults to none, which is a valid digest: the
    #: style's normal editorial behavior and the default general reader.
    reading_instructions: ReadingInstructions | None = None
    root: Path = ROOT
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    rendering: dict[str, Any] | None = None
    #: Data blocks for the stage currently being prepared. Each entry is
    #: ``{tag, payload, source}``; ``source`` describes where the payload came from, which
    #: matters when an artifact was carried forward from an earlier stage.
    pending_blocks: list[dict[str, Any]] = field(default_factory=list)
    #: The run's WOPS adapter, set by the orchestrator after the context is built (the adapter
    #: is created once per run and always exists by the time a stage runs).
    wops: Any = None
    #: The anti-pattern catalogue loaded once per run, cached so the Draft block and the
    #: pipeline record agree on availability and version without re-fetching.
    anti_pattern_catalogue: Any = None
    #: The prevention block's byte budget, resolved from the runtime configuration by the
    #: orchestrator (environment wins, then runtime.json, then the module default).
    anti_pattern_budget_bytes: int | None = None
    #: The Draft prevention-selection record (the ``anti_pattern_prevention`` block's
    #: ``source``), set by the executor after Draft so Writer Revision can supply the compact
    #: prevention context without re-reading the manifest.
    prevention_record: Mapping[str, Any] | None = None
    #: The Draft prevention-selection decision (availability, selected ids, omission reasons),
    #: stored by ``anti_pattern_prevention_block`` even when the block itself is omitted, so the
    #: draft stage record can persist the decision and the audit trail can distinguish
    #: supplied, omitted-with-reason, and unavailable guidance.
    prevention_selection: dict[str, Any] | None = None
    #: The one actionable reader-review problem Targeted Repair would address, set by the
    #: executor's reader-review branch. The targeted-repair stage's history slice is filtered
    #: against it; ``None`` when the reader review found no actionable problem.
    actionable_issue: dict[str, Any] | None = None
    #: Where ``actionable_issue`` came from: ``recorded`` (set during this execution's reader
    #: review), ``recovered`` (re-read from the persisted review artifact by a resumed run), or
    #: ``None`` while unset. Kept beside the issue so a repeat block evaluation reports the
    #: original provenance rather than mistaking its own cache for a live recording.
    actionable_issue_origin: str | None = None

    def stage_excluded_sections(self, stage_name: str) -> list[str]:
        """Convention composition has no withheld style fragments."""
        return []

    # --- reading instructions -----------------------------------------------------------

    def instructions(self) -> ReadingInstructions:
        """The digest's reading instructions, or an empty set when the digest states none."""
        if self.reading_instructions is None:
            self.reading_instructions = empty_instructions(
                self.digest_id, source=self.digest_config_relative
            )
        return self.reading_instructions

    def reading_sections(self, stage_name: str) -> tuple[str, ...]:
        """The canonical reading-instruction sections this stage receives."""
        return self.instructions().for_stage(stage_name)

    def reading_instructions_block(self, stage_name: str) -> dict[str, Any] | None:
        """The delimited reading-instruction block for a stage, or ``None`` when empty."""
        text = self.instructions().render_for_stage(stage_name)
        if not text:
            return None
        return {
            "tag": "reading_instructions",
            "payload": text,
            "source": {
                "path": self.digest_config_relative,
                "sections": list(self.reading_sections(stage_name)),
                "version": self.instructions().version,
            },
        }

    def reader_brief(self) -> str:
        """The digest half of the effective Reader Brief: the `## Reader` section, or ``''``.

        The other half is `editorial/shared/reader.md`, which always applies. The
        effective brief is the reader contract narrowed by this text; it is what the writing and
        review stages are given so they all reason from the same reader.
        """
        return self.instructions().reader_section

    # --- callouts -----------------------------------------------------------------------

    def callout_registry(self):
        """The callouts this digest authorizes, resolved from its own `## Optional highlights`.

        The vocabulary is the digest's, not the pipeline's: a digest that invents a new signal
        needs no code change. The registry is built from the section the run actually read.
        """
        from ..config.callouts import registry_for

        return registry_for(
            self.instructions().get("Optional highlights"),
            source=self.digest_config_relative,
        )

    # --- canonical provenance -----------------------------------------------------------

    def published_source_note_manifest(self) -> Mapping[str, Any] | None:
        """Read the exact manifest Publication Verify recorded for the final artifact.

        Render must use the same final-prose manifest that verification audited. The fallback
        keeps offline prompt inspection useful before a publication artifact exists.
        """
        artifact = self.artifacts.get("publication-verify")
        if artifact is None:
            return None
        report_path = artifact.path.parent / "verification.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        manifest = report.get("source_note_manifest") if isinstance(report, Mapping) else None
        return manifest if isinstance(manifest, Mapping) else None

    def source_note_manifest(self):
        """The canonical source-note manifest: one identity per source, per published unit.

        Built from the **revised artifact** — the prose that will actually be published — and
        the reviewed corpus, so the render stage consumes a canonical manifest instead of
        reconstructing identities and URLs from model-written prose (baseline defect D6).
        Writer Revision may reorder, split, merge or reframe units, so the published structure
        is the structure the revised prose has, not the original Frame's. The original Frame
        remains available as planning/audit history.
        """
        from .provenance import build_source_note_manifest_from_prose

        prose = ""
        for name in ("publication-verify", "targeted-repair", "writer-revision"):
            artifact = self.artifacts.get(name)
            if artifact is not None and artifact.text:
                prose = artifact.text
                break
        return build_source_note_manifest_from_prose(
            prose=prose,
            corpus=self.corpus,
            digest_id=self.digest_id,
            style=self.style,
        )

    # --- rendering values ---------------------------------------------------------------

    def rendering_values(self) -> dict[str, Any]:
        """Computed lazily: the digest reading time depends on the approved prose, which does
        not exist until publication-verify has produced it."""
        prose = ""
        for name in ("publication-verify", "targeted-repair", "writer-revision"):
            artifact = self.artifacts.get(name)
            if artifact is not None and artifact.text:
                prose = artifact.text
                break
        resolved = resolve_rendering_values(
            corpus=self.corpus,
            digest_id=self.digest_id,
            digest_name=self.digest_name,
            style=self.style,
            language=self.language,
            body_prose=prose,
        )
        self.rendering = resolved
        return {"run_key": self.run_key, "run_key_source": self.run_key_source, **resolved["values"]}

    def rendering_notes(self) -> list[str]:
        return (self.rendering or {}).get("notes", [])

    # --- data blocks --------------------------------------------------------------------

    @property
    def digest_config_relative(self) -> str:
        return relative_to_root(self.config_path, self.root)

    def artifact_block(self, target: str, tag: str, artifact_name: str | None = None) -> dict[str, Any] | None:
        artifact = self.artifacts.get(target)
        if artifact is None:
            return None
        if artifact_name and artifact.path.name != artifact_name:
            # A stage may declare an extra artifact (e.g. ``wops.json``) that lives beside its
            # primary artifact (``review.json``) in the same output directory. Resolve it by
            # sibling path so the block actually reaches the stage instead of silently dropping.
            sibling = artifact.path.parent / artifact_name
            if not sibling.is_file():
                return None
            try:
                text = sibling.read_text(encoding="utf-8")
            except OSError:
                return None
            return {
                "tag": tag,
                "payload": text,
                "source": {
                    "stage": target,
                    "path": relative_to_root(sibling, self.root),
                    "provenance": artifact.provenance,
                },
            }
        return {
            "tag": tag,
            "payload": artifact.text,
            "source": {
                "stage": target,
                "path": relative_to_root(artifact.path, self.root),
                "provenance": artifact.provenance,
            },
        }

    def anti_pattern_prevention_block(self) -> dict[str, Any] | None:
        """The bounded preventive anti-pattern guidance block for Draft, or ``None``.

        Derived at run time from the WOPS anti-pattern catalogue through the run's adapter; when
        the catalogue is unavailable or empty the block is ``None`` and the prompt is composed
        without it. The block is inert data, wrapped and printed exactly like every other block.

        Fair rotation (Phase 2): the selection consults the least-recently-supplied history from
        prior runs' Draft prompt manifests, scoped to this run's digest and style profile and
        excluding the current run. Missing or corrupted history degrades to the Phase 1
        selection (all eligible entries treated as never supplied, catalogue order) without
        interrupting the run.
        """
        from .anti_patterns import (
            DEFAULT_PREVENTION_BYTES,
            load_catalogue,
            load_prevention_history,
            prevention_block,
        )

        catalogue = self.anti_pattern_catalogue
        if catalogue is None:
            catalogue = load_catalogue(self.wops)
        budget = self.anti_pattern_budget_bytes or DEFAULT_PREVENTION_BYTES
        history = load_prevention_history(
            self.root,
            self.digest_id,
            self.style_profile_id,
            exclude_run_id=self.run_id,
        )
        text, metadata = prevention_block(
            catalogue,
            max_bytes=budget,
            history=history["supplied_at"],
            history_used={
                "runs_consulted": history["runs_consulted"],
                "runs_skipped": history["runs_skipped"],
            },
        )
        decision = {
            "kind": "wops-anti-pattern-catalogue",
            "available": catalogue.available,
            "version": catalogue.version,
            "reason": catalogue.reason,
            **metadata,
        }
        # The selection decision is persisted even when the block is omitted (an unavailable
        # catalogue, or an available one whose budget fits no entry): the audit trail must be
        # able to distinguish supplied guidance, guidance omitted with a recorded reason, and
        # unavailable guidance — an absent block alone carries none of that.
        self.prevention_selection = decision
        if text is None:
            return None
        return {
            "tag": "anti_pattern_prevention",
            "payload": text,
            "source": decision,
        }

    def prevention_context_block(self) -> dict[str, Any] | None:
        """The compact prevention-context block for Writer Revision, or ``None``.

        The anti-pattern ids and one-line summaries previously supplied to Draft, read from the
        run's Draft prevention record — not the full definitions. It is background context, not
        a checklist: Writer Revision repairs diagnosed problems, never mechanically applies a
        previously supplied rule. ``None`` when no prevention record exists.
        """
        from .anti_patterns import load_catalogue

        if self.wops is None:
            return None
        catalogue = self.anti_pattern_catalogue
        if catalogue is None:
            catalogue = load_catalogue(self.wops)
        if not getattr(catalogue, "available", False):
            return None
        # The prevention record is the Draft attempt's manifest block source; the executor
        # reads it and stores it on the context for reuse across stages.
        record = getattr(self, "prevention_record", None)
        if not isinstance(record, Mapping):
            return None
        selected_ids = record.get("selected_ids")
        if not isinstance(selected_ids, list) or not selected_ids:
            return None
        lines: list[str] = []
        for anti_pattern_id in selected_ids:
            entry = catalogue.by_id(str(anti_pattern_id))
            if entry is None:
                continue
            name = str(entry.get("name") or entry.get("id") or "").strip()
            summary = str(entry.get("summary") or "").strip()
            lines.append(f"{name} — {summary}".rstrip(" —"))
        if not lines:
            return None
        return {
            "tag": "anti_pattern_prevention_context",
            "payload": "\n".join(lines),
            "source": {
                "kind": "wops-anti-pattern-prevention-context",
                "selected_ids": [str(item) for item in selected_ids],
                "available": catalogue.available,
                "version": catalogue.version,
            },
        }

    def actionable_problem(self) -> tuple[dict[str, Any] | None, str]:
        """The one actionable reader-review problem, recovered from disk when needed.

        Returns ``(issue, origin)``. ``origin`` is ``recorded`` when the reader review ran in
        this execution (the executor set it), ``recovered`` when a resumed run re-reads it from
        the persisted review artifact — either the flattened ``actionable_issue`` record or,
        for reviews written before that field existed, the location in the first
        ``retry_instructions`` entry — and ``absent`` when no repairable problem exists (the
        normal state for an offline composition or a review that requested no repair).
        """
        if isinstance(self.actionable_issue, Mapping):
            return dict(self.actionable_issue), self.actionable_issue_origin or "recorded"
        reader = self.artifacts.get("reader-review")
        review = reader.json if reader is not None and isinstance(reader.json, Mapping) else None
        if not isinstance(review, Mapping):
            return None, "absent"
        recorded = review.get("actionable_issue")
        if isinstance(recorded, Mapping):
            self.actionable_issue = dict(recorded)
            self.actionable_issue_origin = "recovered"
            return dict(recorded), "recovered"
        instructions = review.get("retry_instructions")
        if isinstance(instructions, list) and instructions:
            text = str(instructions[0]).strip()
            location = text[3:].split(":", 1)[0].strip() if text.startswith("In ") else ""
            issue: dict[str, Any] = {
                "section_id": None if not location or location == "the digest" else location,
                "instruction": text,
            }
            self.actionable_issue = issue
            self.actionable_issue_origin = "recovered"
            return issue, "recovered"
        return None, "absent"

    def targeted_repair_wops_block(self) -> dict[str, Any] | None:
        """The stage-scoped writing-operations slice for Targeted Repair, or ``None``.

        Targeted Repair addresses the one actionable problem the reader review named; it must
        not receive the whole retrieval history. The slice keeps:

        * the unresolved anti-pattern findings relevant to that problem — same section as the
          actionable issue, or, for a document-level problem, every unresolved finding;
        * the operations selected for those findings (or for the actionable section), their
          full delivered definitions, and the candidate pool entries behind them;
        * the retrieval queries for the actionable section.

        A finding with no recorded outcome is treated as unresolved (not evaluated is not
        resolved). When the run resumes directly at this stage, the actionable problem is
        recovered from the persisted review artifact; the recovery origin is recorded. The
        filter itself is recorded in the block's ``source`` so the slice is auditable, and it
        is derived from artifacts that already exist — never persisted as a new artifact
        family. With no actionable problem the full record is returned, with the origin
        recorded rather than assumed.
        """
        raw = self.artifact_block("developmental-review", "writing_operations", "wops.json")
        if raw is None:
            return None
        try:
            wops = json.loads(raw["payload"])
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(wops, Mapping):
            return None
        actionable, origin = self.actionable_problem()
        if not isinstance(actionable, Mapping):
            # No actionable problem: there is no slice to compute. The full record is returned
            # so a composition without one (offline inspection, or a caller that never recorded
            # an actionable problem) does not silently lose the operations; a real Targeted
            # Repair run always has one, so the filtered slice below is what a repair prompt
            # actually carries. The origin is recorded so the state is visible, not silent.
            source = dict(raw.get("source") or {})
            source["history_scope"] = {"stage": "targeted-repair", "origin": origin, "slice": "full"}
            return {**raw, "source": source}
        section_id = actionable.get("section_id") or None

        outcomes: dict[str, str] = {}
        reader = self.artifacts.get("reader-review")
        if reader is not None and isinstance(reader.json, Mapping):
            for outcome in reader.json.get("anti_pattern_outcomes") or []:
                if isinstance(outcome, Mapping) and outcome.get("finding_id"):
                    outcomes[str(outcome["finding_id"])] = str(outcome.get("status") or "")

        def _unresolved(finding_id: str) -> bool:
            return outcomes.get(finding_id) != "resolved"

        findings = [
            finding
            for finding in (wops.get("anti_pattern_findings") or [])
            if isinstance(finding, Mapping)
            and _unresolved(str(finding.get("finding_id") or ""))
            and (section_id is None or finding.get("section_id") == section_id)
        ]
        kept_finding_ids = {
            str(finding["finding_id"]) for finding in findings if finding.get("finding_id")
        }

        kept_selected: list[Mapping[str, Any]] = []
        kept_operation_ids: set[str] = set()
        for entry in wops.get("selected") or []:
            if not isinstance(entry, Mapping):
                continue
            linkage = (entry.get("selected_for") or {}).get("anti_pattern_findings") or []
            linked = {str(item) for item in linkage if item}
            in_section = section_id is not None and section_id in (entry.get("matched_section_ids") or [])
            if not ((linked & kept_finding_ids) or in_section):
                continue
            kept_selected.append(entry)
            if entry.get("id") not in (None, ""):
                kept_operation_ids.add(str(entry["id"]))

        operations = [
            operation
            for operation in (wops.get("operations") or [])
            if isinstance(operation, Mapping) and str(operation.get("id")) in kept_operation_ids
        ]
        queries = [
            query
            for query in (wops.get("queries") or [])
            if isinstance(query, Mapping)
            and (section_id is None or query.get("section_id") == section_id)
        ]
        # The candidate pool is filtered by the same rule, so an unrelated retrieval candidate
        # — including one whose linkage has no kept finding and whose section differs — never
        # reaches the repair prompt.
        candidates = [
            candidate
            for candidate in (wops.get("candidates") or [])
            if isinstance(candidate, Mapping)
            and (
                {str(item) for item in ((candidate.get("matched_finding_ids") or []) if isinstance(candidate.get("matched_finding_ids"), list) else [])} & kept_finding_ids
                or (section_id is not None and section_id in (candidate.get("matched_section_ids") or []))
            )
        ]

        all_findings = wops.get("anti_pattern_findings") or []
        all_operation_ids = {
            str(entry["id"])
            for entry in (wops.get("selected") or [])
            if isinstance(entry, Mapping) and entry.get("id") not in (None, "")
        }
        all_candidate_ids = {
            str(candidate["id"])
            for candidate in (wops.get("candidates") or [])
            if isinstance(candidate, Mapping) and candidate.get("id") not in (None, "")
        }
        filtered = dict(wops)
        filtered["anti_pattern_findings"] = findings
        filtered["selected"] = list(kept_selected)
        filtered["operations"] = operations
        filtered["queries"] = queries
        filtered["candidates"] = candidates
        filtered["history_filter"] = {
            "stage": "targeted-repair",
            "origin": origin,
            "actionable_section_id": section_id,
            "kept_finding_ids": sorted(kept_finding_ids),
            "omitted_finding_ids": sorted(
                str(finding["finding_id"])
                for finding in all_findings
                if isinstance(finding, Mapping)
                and finding.get("finding_id")
                and str(finding["finding_id"]) not in kept_finding_ids
            ),
            "kept_operation_ids": sorted(kept_operation_ids),
            "omitted_operation_ids": sorted(all_operation_ids - kept_operation_ids),
            "kept_candidate_ids": sorted(
                str(candidate["id"])
                for candidate in candidates
                if candidate.get("id") not in (None, "")
            ),
            "omitted_candidate_ids": sorted(
                all_candidate_ids
                - {str(candidate["id"]) for candidate in candidates if candidate.get("id") not in (None, "")}
            ),
        }
        source = dict(raw.get("source") or {})
        source["filtered_for"] = {
            "stage": "targeted-repair",
            "origin": origin,
            "actionable_section_id": section_id,
            "kept_finding_ids": sorted(kept_finding_ids),
        }
        return {"tag": "writing_operations", "payload": json.dumps(filtered, ensure_ascii=False, indent=2), "source": source}


__all__ = ["Artifact", "RunContext"]
