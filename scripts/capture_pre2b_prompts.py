#!/usr/bin/env python
"""Capture the exact pre-Phase-2b prompts, from inside the historical worktree.

Run with the pre-2b commit checked out:

    git worktree add ../digy-pre2b 8ad4287
    python ../digy-pre2b/scripts/capture_pre2b_prompts.py --output tests/fixtures/phase2b/pre2b-prompts.json

This reconstructs each stage's system and user prompt exactly as the pre-Jinja2 executor built
it — the preamble, the inlined documents, the evidence projection, the data blocks, the task
block — using the same synthetic corpus the frozen migration reference was built from, so the
capture needs no run directory and no credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from digest_system.config.profiles import STYLE_PROFILES, style_profile_ids  # noqa: E402
from digest_system.editorial.evidence.projection import project_evidence  # noqa: E402
from digest_system.editorial.prompts.assembler import (  # noqa: E402
    assemble_stage_context,
    required_block,
    stage_task_block,
    system_preamble,
)
from digest_system.editorial.stages import stage_names_v2, stage_v2  # noqa: E402
from digest_system.runtime.artifacts import wrap_block  # noqa: E402

DIGEST_CONFIG_BY_STYLE = {
    "synthesis-max": "digests/tech-bi-daily.md",
    "curated-discovery": "digests/medium-bi-daily.md",
    "concise": "digests/tech-bi-daily.md",
    "detailed": "digests/tech-bi-daily.md",
}


class _Ctx:
    """The stage-context slice the pre-2b assembler and executor read."""

    def __init__(self, *, style, profile, digest_config_relative, artifacts):
        self.digest_id = "tech-bi-daily"
        self.style = style
        self.language = "English"
        self.profile = profile
        self.digest_config_relative = digest_config_relative
        self.artifacts = artifacts
        self.root = ROOT

    def style_documents(self, name):
        from digest_system.config.profiles import preflight_style_profile

        preflight = preflight_style_profile(self.profile, root=ROOT)
        return [
            entry.descriptor.to_dict()
            for entry in preflight.stages.get(name, {}).get("documents", [])
        ]

    def style_contracts(self, name):
        from digest_system.config.profiles import preflight_style_profile

        preflight = preflight_style_profile(self.profile, root=ROOT)
        resolved = preflight.stages.get(name, {}).get("contracts", {})
        return {key: entry.descriptor.to_dict() for key, entry in resolved.items()}

    def rendering_documents(self):
        return [{"path": self.profile.rendering["rules"]}, {"path": self.profile.rendering["template"]}]

    def stage_excluded_sections(self, name):
        from digest_system.config.profiles import excluded_sections

        preflight = preflight_style_profile(self.profile, root=ROOT)
        return excluded_sections(profile=self.profile, stage=name, style_headings=preflight.style_headings)

    def artifact_block(self, target, tag, artifact_name=None):
        artifact = self.artifacts.get(target)
        if artifact is None:
            return None
        if artifact_name and Path(artifact["path"]).name != artifact_name:
            return None
        return {
            "tag": tag,
            "payload": artifact["text"],
            "source": {"stage": target, "path": artifact["path"], "provenance": "runner"},
        }

    def rendering_values(self):
        return {"run_key": "synthetic-run-key", "run_key_source": "fixture"}

    def rendering_notes(self):
        return []


def _synth_artifacts():
    sys.path.insert(0, str(ROOT))
    from tests.python.fixtures import analysis_valid, corpus, frame_valid

    prose = "\n".join(
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
    return {
        "source-acquisition": {"path": "source-acquisition/sources.json", "text": json.dumps(corpus(), indent=2)},
        "analyze": {"path": ".digest-runs/x/analyze/output/analysis.json", "text": json.dumps(analysis_valid(), indent=2)},
        "frame": {"path": ".digest-runs/x/frame/output/frame.json", "text": json.dumps(frame_valid(), indent=2)},
        "draft": {"path": ".digest-runs/x/draft/output/draft.md", "text": prose},
        "writer-revision": {"path": ".digest-runs/x/writer-revision/output/revision.md", "text": prose},
        "line-edit": {"path": ".digest-runs/x/line-edit/output/line-edit.md", "text": prose},
        "copy-verify": {"path": ".digest-runs/x/copy-verify/output/final.md", "text": prose},
        "developmental-review": {
            "path": ".digest-runs/x/developmental-review/output/review.json",
            "text": json.dumps({"issues": [], "revision_priorities": []}, indent=2),
        },
        "reader-review": {
            "path": ".digest-runs/x/reader-review/output/review.json",
            "text": json.dumps({"status": "preserved", "material_regression": False}, indent=2),
        },
    }


def _json_corpus():
    from tests.python.fixtures import corpus, frame_valid

    return corpus(), frame_valid()


def capture_stage(stage_name, profile, config):
    stage = stage_v2(stage_name)
    corpus, frame = _json_corpus()
    ctx = _Ctx(
        style=profile.style,
        profile=profile,
        digest_config_relative=config,
        artifacts=_synth_artifacts() | {"frame-json": {"path": "f.json", "text": ""}},
    )
    ctx.artifacts["frame"]["json"] = frame
    ctx.artifacts["analyze"]["json"] = json.loads(ctx.artifacts["analyze"]["text"])
    documents = assemble_stage_context(
        stage_name=stage_name, profile=profile, digest_config_relative=config
    )
    if stage.executor == "evaluation":
        return {"executor": stage.executor, "contracts": documents["contracts"]}

    projection = None
    if stage.corpus != "none":
        analysis = ctx.artifacts["analyze"].get("json")
        projection = project_evidence(corpus=corpus, stage=stage, frame=frame, analysis=analysis)
    blocks = required_block(stage.blocks(ctx))
    corpus_block = wrap_block("source_corpus", projection["text"]) if projection and projection["text"] else ""
    system_text = system_preamble(stage, documents["text"])
    entries = [corpus_block, *blocks, stage_task_block(stage, ctx)]
    user_text = "\n\n".join(
        entry if isinstance(entry, str) else wrap_block(entry["tag"], entry["payload"]) for entry in entries if entry
    )
    return {"executor": stage.executor, "system_text": system_text, "user_text": user_text}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    profiles = {}
    for profile_id in style_profile_ids():
        profile = STYLE_PROFILES[profile_id]
        config = DIGEST_CONFIG_BY_STYLE[profile.style]
        profiles[profile_id] = {
            name: capture_stage(name, profile, config) for name in stage_names_v2()
        }

    from evaluation.semantic.developmental import BUILTIN_PROBLEM_TYPES, developmental_prompt
    from evaluation.semantic.prompts import absolute_prompt, comparison_prompt
    from evaluation.sections import parse_sections

    text = "\n".join(
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
    parsed = parse_sections(text, style="synthesis-max", prepare=True)
    sections = list(parsed.sections)
    evaluation = {
        "developmental": developmental_prompt(
            draft_text=text, frame_text="", frame_json=None, sections=sections,
            problem_types=BUILTIN_PROBLEM_TYPES,
        ),
        "absolute": absolute_prompt(digest_text=text, sections=sections, style="synthesis-max"),
        "comparison": comparison_prompt(
            before_text=text, after_text=text, before_sections=sections, after_sections=sections,
            style="synthesis-max",
        ),
    }

    payload = {
        "schema_version": 1,
        "generated_by": "scripts/capture_pre2b_prompts.py at 8ad4287",
        "note": "The exact pre-Jinja2 prompts, with a synthetic context. Packaging may change.",
        "profiles": profiles,
        "evaluation": evaluation,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(profiles)} profiles, {sum(len(v) for v in profiles.values())} stages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
