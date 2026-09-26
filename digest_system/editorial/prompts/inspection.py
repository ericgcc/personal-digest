"""Offline prompt inspection: what a stage will actually send, and where every part came from.

The core result of Phase 2b is that a developer can open a stage template, read its declared
dependencies, inspect the profile that selects them, and generate exactly what the model will
receive — without reading the executor and without spending anything.

This module is that interface. For one (digest, profile, stage) it produces:

* the resolved **system** and **user** prompt, byte for byte;
* a machine-readable **manifest** naming every template, instruction file and data block, with
  sizes and content hashes, plus the style modules the profile withheld and why;
* a human-readable **report** an operator can read in a terminal.

For an evaluation stage there is no system/user split: the Python adapter sends one combined
judge prompt. Rather than invent message roles the evaluator does not use, the inspection
renders that single prompt through the same Jinja2 templates and reports it as the combined
prompt it is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ...config.profiles import preflight_style_profile, style_profile_for
from ...runtime.artifacts import ROOT, RunnerError
from ..evaluation_prompts import compose_evaluation_prompts
from ..stages import stage_names_v2, stage_v2
from .compose import ComposedPrompt, compose_stage_prompt
from .offline import OfflineContext, build_context, seed_artifacts, stage_inputs


@dataclass
class Inspection:
    """One stage's resolved prompt and its dependency manifest."""

    digest_id: str
    style: str
    profile_id: str
    profile_version: str
    stage: str
    executor: str
    #: The two messages, for a stage the model executes directly.
    system_text: str = ""
    user_text: str = ""
    #: The combined prompt, for a stage the Python evaluator executes.
    combined_text: str = ""
    manifest: dict[str, Any] = field(default_factory=dict)
    report: str = ""

    @property
    def prompt_text(self) -> str:
        if self.combined_text:
            return self.combined_text
        return f"{self.system_text}\n\n=== USER ===\n\n{self.user_text}"

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "digest_id": self.digest_id,
            "style": self.style,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "stage": self.stage,
            "executor": self.executor,
            "manifest": self.manifest,
        }
        if self.combined_text:
            value["combined_text"] = self.combined_text
        else:
            value["system_text"] = self.system_text
            value["user_text"] = self.user_text
        return value

    def write(self, directory: Path) -> list[Path]:
        """Write ``system.txt``/``user.txt`` (or ``prompt.txt``), ``manifest.json`` and ``report.md``."""
        directory.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        if self.combined_text:
            (directory / "prompt.txt").write_text(self.combined_text, encoding="utf-8", newline="\n")
            written.append(directory / "prompt.txt")
        else:
            (directory / "system.txt").write_text(self.system_text, encoding="utf-8", newline="\n")
            (directory / "user.txt").write_text(self.user_text, encoding="utf-8", newline="\n")
            written.extend([directory / "system.txt", directory / "user.txt"])
        (directory / "manifest.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (directory / "report.md").write_text(self.report, encoding="utf-8", newline="\n")
        written.extend([directory / "manifest.json", directory / "report.md"])
        return written


def _style_manifest(style: str, *, root: Path) -> dict[str, Any]:
    from ...config.style_modules import load_style_manifest

    manifest = load_style_manifest(style, root=root)
    return {
        "document": manifest.document,
        "directory": manifest.directory,
        "modules": [
            {"file": module.file, "heading": module.heading, "sha256": _digest(root / module.file)}
            for module in manifest.modules
        ],
    }


def _digest(path: Path) -> str:
    import hashlib

    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(inspection: Inspection, *, style_manifest: dict[str, Any], profile: Any) -> str:
    manifest = inspection.manifest
    lines = [
        f"# Prompt inspection — {inspection.profile_id} / {inspection.stage}",
        "",
        f"- Digest: `{inspection.digest_id}`",
        f"- Style: `{inspection.style}`",
        f"- Profile: `{inspection.profile_id}` v{inspection.profile_version} ({profile.status})",
        f"- Stage: `{inspection.stage}` (executor `{inspection.executor}`)",
        f"- Message: {'one combined judge prompt' if inspection.combined_text else 'system + user'}",
        "",
        "## Templates",
        "",
    ]
    for entry in manifest.get("templates", []):
        lines.append(f"- `{entry['path']}` — {entry['bytes']} units, sha256 `{entry['sha256'][:12]}`")
    lines += ["", "## Instruction documents", ""]
    documents = manifest.get("documents", [])
    if not documents:
        lines.append("- (none)")
    for entry in documents:
        lines.append(f"- `{entry['path']}` — {entry['bytes']} chars, sha256 `{entry['sha256'][:12]}`")
    instructions = manifest.get("instructions", [])
    lines += ["", "## Style-supplied instructions", ""]
    if not instructions:
        lines.append("- (none: this stage receives no style-specific document under this profile)")
    for entry in instructions:
        lines.append(f"- `{entry['path']}` — {entry['bytes']} chars, sha256 `{entry['sha256'][:12]}`")
    omitted = manifest.get("omitted", [])
    lines += ["", "## Deliberately omitted style modules", ""]
    if not omitted:
        lines.append("- (none: this profile supplies every module the stage receives)")
    for path in omitted:
        lines.append(f"- `{path}`")
    lines += ["", "## Data blocks", ""]
    blocks = manifest.get("blocks", [])
    if not blocks:
        lines.append("- (none)")
    for entry in blocks:
        lines.append(f"- `{entry['tag']}` — {entry['bytes']} chars")
    lines += [
        "",
        "## Sizes",
        "",
        f"- System: {manifest.get('system_bytes', 0)} units",
        f"- User: {manifest.get('user_bytes', 0)} units",
        "",
        "## Style modules",
        "",
        f"- Document: `{style_manifest['document']}` (generated from `{style_manifest['directory']}`)",
    ]
    for module in style_manifest["modules"]:
        lines.append(f"  - `{module['file']}` — {module['heading']}")
    lines.append("")
    return "\n".join(lines)


def inspect_stage(
    *,
    digest_id: str,
    profile_id: str,
    stage_name: str,
    root: Path | None = None,
    context: OfflineContext | None = None,
    evaluation_inputs: Mapping[str, Any] | None = None,
) -> Inspection:
    """Resolve one stage's prompt for one profile, with no model call and no run directory.

    ``digest_id`` is recorded for the report and, where a digest configuration exists, is used
    to resolve the digest's config document; it does not otherwise alter composition.
    """
    base = root or ROOT
    profile = style_profile_for(profile_id)
    if profile is None:
        raise RunnerError(f"Unknown style profile {profile_id!r}")
    if stage_name not in stage_names_v2():
        raise RunnerError(f"Unknown stage {stage_name!r}")

    stage = stage_v2(stage_name)
    offline = context or build_context(profile=profile, root=base)
    offline.digest_id = digest_id
    seed_artifacts(offline)

    style_manifest = _style_manifest(profile.style, root=base)
    preflight_style_profile(profile, root=base)

    if stage.executor == "evaluation":
        inputs = stage_inputs(stage_name, offline)
        contracts = inputs["documents"]["contracts"]
        evaluation = evaluation_inputs or {}
        prompts = compose_evaluation_prompts(
            command=evaluation.get("command") or _command_for(stage_name),
            contracts=contracts,
            style=profile.style,
            language=offline.language,
            draft_text=evaluation.get("draft_text", SYNTHETIC_DRAFT_FOR_EVALUATION),
            before_text=evaluation.get("before_text", SYNTHETIC_DRAFT_FOR_EVALUATION),
        )
        manifest = {
            "system_template": None,
            "user_template": None,
            "templates": [
                {"path": f"prompts/{path}", "bytes": 0, "sha256": _digest(base / "prompts" / path)}
                for path in prompts.templates
            ],
            "documents": [],
            "instructions": [
                {
                    "path": entry["path"],
                    "bytes": entry["bytes"],
                    "sha256": _digest(base / entry["path"]),
                }
                for entry in inputs["documents"]["manifest"]
            ],
            "blocks": [],
            "omitted": inputs["documents"]["excluded_sections"],
            "system_bytes": 0,
            "user_bytes": 0,
        }
        inspection = Inspection(
            digest_id=digest_id,
            style=profile.style,
            profile_id=profile.id,
            profile_version=profile.version,
            stage=stage_name,
            executor=stage.executor,
            combined_text=prompts.prompt,
            manifest=manifest,
        )
        inspection.report = _report(inspection, style_manifest=style_manifest, profile=profile)
        return inspection

    inputs = stage_inputs(stage_name, offline)
    extra_blocks = _extra_blocks(stage_name, offline)
    composed: ComposedPrompt = compose_stage_prompt(
        stage=stage,
        context=offline,
        documents=inputs["documents"],
        projection=inputs["projection"],
        blocks=stage.blocks(offline),
        extra_blocks=extra_blocks,
    )
    manifest = composed.manifest.to_dict()
    manifest["omitted"] = inputs["documents"]["excluded_sections"]
    inspection = Inspection(
        digest_id=digest_id,
        style=profile.style,
        profile_id=profile.id,
        profile_version=profile.version,
        stage=stage_name,
        executor=stage.executor,
        system_text=composed.system_text,
        user_text=composed.user_text,
        manifest=manifest,
    )
    inspection.report = _report(inspection, style_manifest=style_manifest, profile=profile)
    return inspection


SYNTHETIC_DRAFT_FOR_EVALUATION = "\n".join(
    [
        "## THE BIG PICTURE",
        "",
        "Incremental evaluation changes what a claim costs to check, and the change is not uniform.",
        "",
        "## Incremental evaluation",
        "",
        "The mechanism makes the claim checkable [1]. The qualifier narrows it [2].",
    ]
)


def _command_for(stage_name: str) -> str:
    return "evaluate-developmental-review" if stage_name == "developmental-review" else "compare-reader-quality"


def _extra_blocks(stage_name: str, context: OfflineContext) -> dict[str, Any]:
    """The stage-specific blocks the executor computes outside the stage declaration."""
    if stage_name == "copy-verify":
        return {
            "deterministic_check_findings": json.dumps({"counts": {}, "checks": []}, indent=2),
            "approved_frame_citations": json.dumps({"declared_source_numbers": [1, 2, 3, 5]}, indent=2),
        }
    if stage_name == "render":
        return {"rendering_values": json.dumps(context.rendering_values(), ensure_ascii=False, indent=2)}
    return {}


def inspect_all(
    *,
    digest_id: str,
    profile_id: str,
    root: Path | None = None,
) -> list[Inspection]:
    return [
        inspect_stage(digest_id=digest_id, profile_id=profile_id, stage_name=name, root=root)
        for name in stage_names_v2()
    ]


__all__ = ["Inspection", "inspect_all", "inspect_stage"]
