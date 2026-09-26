"""Discovery and parsing of the historical ``.digest-runs`` corpus.

The loader derives everything from real pipeline metadata:

* the ordered stage list and stage artifact filenames come from the static v1
  descriptor at ``config/pipeline-v1-stages.json`` — preserved as data so historical
  runs that predate ``run-summary.json`` stage records remain describable without an
  executable v1 runner;
* a run's own stage order comes from its ``run-summary.json``, which the runner
  writes only when a pipeline completes;
* the digest language and style come from the digest frontmatter the pipeline
  itself reads during preflight.

Filenames are never used to guess a stage or a run's completeness.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml

from ..config import ProjectPaths, default_paths
from ..languages import resolve_language
from .run_model import (
    DigestConfig,
    HistoricalRun,
    StageArtifact,
    StageSpec,
    artifact_kind,
)

_STAGES_BLOCK = re.compile(r"const\s+STAGES\s*=\s*\[(.*?)\n\];", re.DOTALL)
_STAGE_ENTRY = re.compile(
    r"\[\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"\s*,\s*\"([^\"]*)\"\s*\]"
)
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_PHASE_HEADING = re.compile(r"^#{1,6}\s+(?:\d+\.\s*)?([A-Za-z][A-Za-z&\s]*?)\s*(?:[—–-]{1,2}|$)")


def parse_stage_specs(runner_path: str | Path) -> tuple[StageSpec, ...]:
    """Parse the ordered stage list from the static v1 descriptor.

    ``runner_path`` is accepted for compatibility with the historical call shape; the
    stage list itself is read from ``config/pipeline-v1-stages.json`` beside the
    project root, which is the one authoritative copy of the retired v1 stage table.

    Raises:
        FileNotFoundError: the descriptor is missing.
        ValueError: the descriptor exists but declares no stages.
    """
    path = Path(runner_path)
    # `runner_path` is `<root>/tools/digest_runner.mjs`, so the project root is its
    # grandparent directory.
    root = path.parents[1].resolve()
    descriptor = (root / "config" / "pipeline-v1-stages.json").resolve()
    if not descriptor.is_file():
        raise FileNotFoundError(f"v1 stage descriptor missing: {descriptor}")
    raw = json.loads(descriptor.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"v1 stage descriptor at {descriptor} is not a list")
    specs = tuple(
        StageSpec(
            name=str(entry["name"]),
            artifact=str(entry["artifact"]),
            declared_type=str(entry["type"]),
            task=str(entry.get("task", "")),
        )
        for entry in raw
    )
    if not specs:
        raise ValueError(f"No stage entries in the v1 descriptor {descriptor}")
    return specs


def parse_frontmatter(text: str) -> dict[str, object]:
    """Parse YAML frontmatter from a Markdown document.

    Returns an empty mapping when no frontmatter is present or when it is not a
    mapping, so a malformed digest file degrades to "no metadata" rather than
    aborting the whole historical scan.
    """
    match = _FRONTMATTER.match(text)
    if match is None:
        return {}
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_digest_configs(digests_dir: str | Path) -> dict[str, DigestConfig]:
    """Load every digest configuration keyed by digest ID."""
    directory = Path(digests_dir)
    configs: dict[str, DigestConfig] = {}
    if not directory.is_dir():
        return configs
    for path in sorted(directory.glob("*.md")):
        frontmatter = parse_frontmatter(path.read_text(encoding="utf-8"))
        digest_id = str(frontmatter.get("id") or path.stem)
        aliases_raw = frontmatter.get("aliases") or []
        if isinstance(aliases_raw, str):
            aliases = (aliases_raw,)
        elif isinstance(aliases_raw, Iterable):
            aliases = tuple(str(alias) for alias in aliases_raw)
        else:  # pragma: no cover - defensive
            aliases = ()
        language_raw = frontmatter.get("language")
        enabled_raw = frontmatter.get("enabled", True)
        configs[digest_id] = DigestConfig(
            digest_id=digest_id,
            path=path,
            name=str(frontmatter["name"]) if frontmatter.get("name") else None,
            style=str(frontmatter["style"]) if frontmatter.get("style") else None,
            language_raw=str(language_raw) if language_raw is not None else None,
            enabled=bool(enabled_raw),
            aliases=aliases,
        )
    return configs


def load_registry(registry_path: str | Path) -> dict[str, object]:
    """Load ``system/registry.yaml`` as a plain mapping."""
    path = Path(registry_path)
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _registry_language(registry: Mapping[str, object], digest_id: str | None) -> str | None:
    digests = registry.get("digests")
    if digest_id and isinstance(digests, Mapping):
        entry = digests.get(digest_id)
        if isinstance(entry, Mapping) and entry.get("language"):
            return str(entry["language"])
    defaults = registry.get("defaults")
    if isinstance(defaults, Mapping) and defaults.get("language"):
        return str(defaults["language"])
    return None


def load_editorial_phases(editorial_process_path: str | Path) -> dict[str, str]:
    """Map a normalized phase verb to its editorial-process heading.

    The mapping is derived from ``system/editorial-process.md`` so stage names
    are never duplicated in code. ``voice-edit`` resolves to the
    ``VOICE & NATURALNESS EDIT`` phase because both share the ``voice`` verb.
    """
    path = Path(editorial_process_path)
    phases: dict[str, str] = {}
    if not path.is_file():
        return phases
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _PHASE_HEADING.match(line.strip())
        if not match:
            continue
        label = match.group(1).strip()
        verb = label.split()[0].lower() if label else ""
        if verb:
            phases[verb] = label.upper()
    return phases


def phase_for_stage(stage_name: str, phases: Mapping[str, str]) -> str | None:
    """Resolve a stage name to its editorial-process phase label."""
    verb = stage_name.split("-")[0].lower()
    return phases.get(verb)


def _discover_artifact(
    run_dir: Path, stage_name: str, expected_artifact: str
) -> Path | None:
    """Find a stage's output artifact without guessing the stage from a filename."""
    output_dir = run_dir / stage_name / "output"
    expected = output_dir / expected_artifact
    if expected.is_file():
        return expected
    if not output_dir.is_dir():
        return None
    candidates = sorted(path for path in output_dir.iterdir() if path.is_file())
    if len(candidates) == 1:
        # Tolerate a renamed artifact inside the stage's own output directory,
        # but never scan outside it: the stage directory is the real signal.
        return candidates[0]
    return None


def _infer_digest_id(run_dir_name: str, configs: Mapping[str, DigestConfig]) -> str | None:
    """Infer a digest ID from a run directory name using configured identities."""
    identities: list[tuple[str, str]] = []
    for config in configs.values():
        identities.append((config.digest_id, config.digest_id))
        for alias in config.aliases:
            identities.append((alias, config.digest_id))
    best: tuple[int, str] | None = None
    for identity, digest_id in identities:
        if run_dir_name == identity or run_dir_name.startswith(f"{identity}-"):
            if best is None or len(identity) > best[0]:
                best = (len(identity), digest_id)
    return best[1] if best else None


def _digest_from_context(run_dir: Path) -> str | None:
    """Recover the digest identity from the instructions the runner inlined.

    Every stage copies the canonical digest config it was given into
    ``<stage>/context/digests/<digest-id>.md``. That copy is real pipeline
    metadata, so it identifies runs that never wrote a ``run-summary.json``
    (interrupted runs and older replay fixtures) without guessing from the
    directory name.
    """
    if not run_dir.is_dir():
        return None
    for stage_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        digests_dir = stage_dir / "context" / "digests"
        if not digests_dir.is_dir():
            continue
        stems = sorted(md.stem for md in digests_dir.glob("*.md"))
        if stems:
            return stems[0]
    return None


def _load_summary(summary_path: Path) -> dict[str, object]:
    if not summary_path.is_file():
        return {}
    try:
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _summary_stage_order(summary: Mapping[str, object]) -> list[str]:
    stages = summary.get("stages")
    if not isinstance(stages, list):
        return []
    order: list[str] = []
    for entry in stages:
        if isinstance(entry, Mapping) and entry.get("stage"):
            order.append(str(entry["stage"]))
    return order


def load_run(
    run_dir: Path,
    stage_specs: Sequence[StageSpec],
    digest_configs: Mapping[str, DigestConfig],
    registry: Mapping[str, object],
    phases: Mapping[str, str],
) -> HistoricalRun:
    """Load a single run directory into a :class:`HistoricalRun`."""
    summary_path = run_dir / "run-summary.json"
    summary = _load_summary(summary_path)
    notes: list[str] = []

    digest_id = str(summary["digest_id"]) if summary.get("digest_id") else None
    if digest_id is None:
        digest_id = _digest_from_context(run_dir)
        if digest_id is not None:
            notes.append("digest_id recovered from inlined stage context; no run summary.")
    if digest_id is None:
        digest_id = _infer_digest_id(run_dir.name, digest_configs)
        if digest_id is not None:
            notes.append("digest_id inferred from run directory name; no run summary.")
    config = digest_configs.get(digest_id) if digest_id else None

    style = str(summary["style"]) if summary.get("style") else None
    if style is None and config is not None:
        style = config.style

    spec_by_name = {spec.name: spec for spec in stage_specs}
    declared_order = _summary_stage_order(summary)
    if declared_order:
        # Preserve the run's real order, then append any declared stage the
        # summary did not mention so newer pipeline stages stay visible.
        ordered_names = list(declared_order)
        ordered_names.extend(
            spec.name for spec in stage_specs if spec.name not in ordered_names
        )
    else:
        ordered_names = [spec.name for spec in stage_specs]
        notes.append("stage order taken from the pipeline STAGES declaration.")

    stages: list[StageArtifact] = []
    for index, stage_name in enumerate(ordered_names):
        spec = spec_by_name.get(stage_name)
        declared_type = spec.declared_type if spec else ""
        expected_artifact = spec.artifact if spec else ""
        artifact_path = (
            _discover_artifact(run_dir, stage_name, expected_artifact)
            if expected_artifact
            else None
        )
        stages.append(
            StageArtifact(
                run_id=run_dir.name,
                digest_id=digest_id,
                stage_index=index,
                stage_name=stage_name,
                declared_type=declared_type,
                kind=artifact_kind(declared_type),
                expected_artifact=expected_artifact,
                artifact_path=artifact_path,
                editorial_phase=phase_for_stage(stage_name, phases),
            )
        )

    language = resolve_language(
        (
            (config.language_raw, "digest-config") if config else (None, "digest-config"),
            (
                str(summary["language"]) if summary.get("language") else None,
                "run-metadata",
            ),
            (_registry_language(registry, digest_id), "registry-defaults"),
        )
    )

    complete = summary_path.is_file() and all(stage.available for stage in stages)
    if not summary_path.is_file():
        notes.append("no run-summary.json: run did not complete through the pipeline.")
    elif not complete:
        missing = [stage.stage_name for stage in stages if not stage.available]
        notes.append(
            "run summary exists but these stage artifacts are missing: "
            + ", ".join(missing)
        )

    return HistoricalRun(
        run_id=run_dir.name,
        run_dir=run_dir,
        digest_id=digest_id,
        style=style,
        complete=complete,
        stages=tuple(stages),
        language=language,
        digest_config=config,
        summary_path=summary_path if summary_path.is_file() else None,
        started_at=str(summary["started_at"]) if summary.get("started_at") else None,
        completed_at=str(summary["completed_at"]) if summary.get("completed_at") else None,
        notes=tuple(notes),
    )


def discover_runs(
    paths: ProjectPaths | None = None,
    *,
    stage_specs: Sequence[StageSpec] | None = None,
) -> list[HistoricalRun]:
    """Discover every run directory under ``.digest-runs``."""
    resolved = paths or default_paths()
    specs = tuple(stage_specs) if stage_specs is not None else parse_stage_specs(resolved.runner_path)
    configs = load_digest_configs(resolved.digests_dir)
    registry = load_registry(resolved.registry_path)
    phases = load_editorial_phases(resolved.editorial_process_path)

    runs_dir = resolved.runs_dir
    if not runs_dir.is_dir():
        return []

    runs = [
        load_run(entry, specs, configs, registry, phases)
        for entry in sorted(runs_dir.iterdir())
        if entry.is_dir()
    ]
    runs.sort(key=lambda run: (run.digest_id or "", run.sort_key))
    return runs


def latest_complete_runs(
    runs: Sequence[HistoricalRun], per_digest: int = 3
) -> list[HistoricalRun]:
    """Return the latest ``per_digest`` complete runs for each digest ID."""
    grouped: dict[str, list[HistoricalRun]] = {}
    for run in runs:
        if not run.complete or not run.usable:
            continue
        grouped.setdefault(run.digest_id or "unknown", []).append(run)
    selected: list[HistoricalRun] = []
    for digest_id in sorted(grouped):
        ordered = sorted(grouped[digest_id], key=lambda run: run.sort_key, reverse=True)
        selected.extend(reversed(ordered[: max(per_digest, 0)]))
    selected.sort(key=lambda run: (run.digest_id or "", run.sort_key))
    return selected


def select_runs(
    runs: Sequence[HistoricalRun],
    *,
    run_ids: Sequence[str] | None = None,
    digest_ids: Sequence[str] | None = None,
    last_runs: int | None = None,
    complete_only: bool = False,
) -> list[HistoricalRun]:
    """Filter a discovered run list by explicit IDs, digest, or recency."""
    selected = list(runs)
    if run_ids:
        wanted = set(run_ids)
        selected = [run for run in selected if run.run_id in wanted]
    if digest_ids:
        wanted_digests = set(digest_ids)
        selected = [run for run in selected if run.digest_id in wanted_digests]
    if complete_only:
        selected = [run for run in selected if run.complete]
    if last_runs is not None:
        selected = latest_complete_runs(selected, per_digest=last_runs)
    return selected


def describe_corpus(runs: Sequence[HistoricalRun]) -> dict[str, object]:
    """Summarize a discovered corpus for reporting and CLI output."""
    by_style: dict[str, int] = {}
    by_digest: dict[str, int] = {}
    usable = 0
    complete = 0
    unknown_language = 0
    for run in runs:
        by_style[run.style or "unknown"] = by_style.get(run.style or "unknown", 0) + 1
        by_digest[run.digest_id or "unknown"] = by_digest.get(run.digest_id or "unknown", 0) + 1
        usable += int(run.usable)
        complete += int(run.complete)
        unknown_language += int(not run.language.known)
    return {
        "run_count": len(runs),
        "usable_run_count": usable,
        "complete_run_count": complete,
        "runs_without_resolved_language": unknown_language,
        "by_digest": by_digest,
        "by_style": by_style,
    }
