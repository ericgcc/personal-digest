# Phase 2b — Explicit prompt templates and shared editorial instructions

**Status:** complete. **Branch:** `feat/rework-programmatic-workflow`.

The core result: **Python owns execution, Jinja2 owns composition, Markdown owns editorial
knowledge, and explicit profile configuration determines exactly what each stage receives.**

The ten-stage pipeline, the editorial criteria, the source-selection behaviour and the
OpenRouter provider migration are all out of scope and unchanged. OpenRouter is recorded below
as a separate, both-sides change.

## 1. What changed, in one picture

| Layer | Owns | Lives in |
| --- | --- | --- |
| Python | Execution: stage order, corpus policy, validation, retries, timing, cost | `digest_system/` |
| Jinja2 | Composition: how a stage's instruction is framed | `prompts/` |
| Markdown | Editorial knowledge: what each rule says | `system/`, `styles/` |
| Declarative config | Which instruction reaches which stage | `prompts/profiles/*.yaml`, `styles/<style>/style.yaml` |

Before, a profile named `##` headings inside `styles/<style>.md` and the runtime parsed the
Markdown to extract them. A heading was doing two jobs — editorial formatting and a runtime
identifier — so reorganising a style's prose could silently redirect a stage's instructions.
Now a profile names **files**, and no runtime code parses a heading.

## 2. Instruction-level diff for all five profiles

`python scripts/prompt_diff.py` compares the current prompts against a capture taken at
`8ad4287` (the last commit before any Phase 2b change) and classifies every difference.

```
45/50 profile/stage prompts are packaging-only; 5 approved instruction change(s); 0 unapproved
```

| Profile | Stages packaging-only | Approved instruction changes |
| --- | --- | --- |
| `concise-legacy` | 9 / 10 | 1 — `frame` |
| `curated-discovery-legacy` | 9 / 10 | 1 — `frame` |
| `detailed-legacy` | 9 / 10 | 1 — `frame` |
| `synthesis-max-legacy` | 9 / 10 | 1 — `frame` |
| `synthesis-max-v1` | 9 / 10 | 1 — `frame` |

Packaging-only means the instruction text is identical once document wrappers, file paths and
whitespace are normalized. The single approved change is the same document in every profile:

| Document | Stage | Change | Reason |
| --- | --- | --- | --- |
| `system/style-contract.md` | `frame` | A profile is now said to live in `prompts/profiles/<profile-id>.yaml`, and to select module files rather than headings. | The document told the model that a profile lives in `src/editorial/prompts/style-profiles.mjs`, a path removed when JavaScript was retired. This is step 7's "correct stale instructions", and it is recorded with its reason in `tests/fixtures/phase2b/approved-instruction-changes.json`. |

No other instruction text changed. The tool exits non-zero on an unapproved change, and
`tests/python/regression/test_phase2b_checklist.py` asserts that.

Regenerate with:

```powershell
python scripts/prompt_diff.py                 # human-readable, exits non-zero on a defect
python scripts/prompt_diff.py --json          # machine-readable
python scripts/prompt_diff.py --profile synthesis-max-v1 --stage draft
```

The pre-Phase-2b capture is `tests/fixtures/phase2b/pre2b-prompts.json`, produced by
`scripts/capture_pre2b_prompts.py` run inside a worktree at `8ad4287`.

## 3. Files that became authoritative

| File | New authority |
| --- | --- |
| `prompts/profiles/<profile-id>.yaml` | Which files each stage of each profile receives |
| `styles/<style>/style.yaml` | Which modules compose a style, in order |
| `styles/<style>/modules/*.md` | The individual rules of a style |
| `prompts/stages/<stage>/system.j2` | A stage's shared contract, standards and style instructions |
| `prompts/stages/<stage>/user.j2` | A stage's evidence and previous-artifact declarations |
| `prompts/shared/{preamble,task}.j2` | The framing every stage shares |
| `prompts/evaluation/{developmental,absolute,comparison}.j2` | The evaluator's three judge prompts |
| `prompts/evaluation/shared/*.j2` | The evaluator's rubrics, taxonomy and reader test |
| `digest_system/editorial/prompts/environment.py` | The strict, restricted template environment |
| `digest_system/editorial/prompts/compose.py` | Prompt composition and its dependency manifest |
| `digest_system/editorial/prompts/offline.py` | Offline composition fixtures |
| `digest_system/editorial/prompts/inspection.py` | Offline prompt inspection |
| `digest_system/editorial/prompts/baseline.py` | The recorded baseline |
| `digest_system/config/style_modules.py` | Style module manifests |
| `digest_system/config/legacy.py` | The frozen pre-Phase-2b section vocabulary (reference only) |
| `digest_system/editorial/evaluation_prompts.py` | The evaluator's prompt seam |
| `evaluation/adapters/interface.py` | The evaluator's supported in-process interface |

Generated and verified, not hand-edited: `styles/<style>.md` (from its modules) and
`prompts/profiles/*.yaml` (from `scripts/export_profiles.py`).

## 4. Files removed from the old assembler

| Removed | Was | Replaced by |
| --- | --- | --- |
| `runtime/artifacts.extract_context_sections` | Parsed `##` sections out of a style document | A profile naming module files |
| `runtime/artifacts.extract_sections` | The heading scanner behind it | — |
| `runtime/artifacts.read_context_files` | Unused whole-file reader | The template environment's loader |
| `config/profiles.extract_section_headings` | Runtime heading enumeration | `styles/<style>/style.yaml` |
| `config.profiles.*_SECTIONS` constants | Hardcoded section sets | `prompts/profiles/*.yaml` |
| `prompts/assembler.required_block`, `stage_task_block`, `system_preamble` | Prompt-construction strings in code | `prompts/shared/{preamble,task}.j2` |
| `config/profiles._legacy_profile`, `_synthesis_max_v1`, `_build_profile` | Profiles built in Python | Declarative YAML |
| `evaluation/semantic/prompts.py` prompt literals | The judge prompt text | `prompts/evaluation/*.j2` |
| `evaluation/semantic/developmental.py` `_ISSUE_SHAPE`, `DISCIPLINE` literals | The developmental prompt text | `prompts/evaluation/developmental.j2`, `.../shared/developmental_discipline.j2` |
| `digest_system` importing `evaluation.adapters.cli._HANDLERS` | A private cross-package dependency | `evaluation.adapters.invoke` |

`Descriptor` no longer has a `sections` field at all: a test asserts the model has no concept of
a section, so a Markdown heading cannot become a runtime identifier again.

## 5. Findings from the handoff, addressed

### Evaluation timeouts and audit timing

The adapter no longer reaches into `evaluation.adapters.cli._HANDLERS`. It calls
`evaluation.adapters.invoke`, a documented in-process interface that the standalone CLI also
uses, so the two cannot drift. Every call now reports:

* **`duration_ms`** — measured around the whole call, including a judge request, replacing the
  hardcoded zero. It is written into both the adapter envelope and the result document.
* **A timeout policy** — `timeout_ms` is the declared budget. A call that overruns it is
  recorded as over-budget in the adapter record and surfaced as a warning, rather than being
  silently accepted or silently ignored. The evaluator's judge client still owns transport
  timeouts, because the evaluator runs in-process on purpose.

### OpenRouter is not yet an end-to-end provider switch

Confirmed and recorded as a **separate, both-sides change**: the editorial executor calls the
DeepSeek integration and the evaluator has its own DeepSeek judge, so switching the editorial
model alone would leave the review stages on the previous provider. Phase 2b touches neither
transport. `docs/architecture/overview.md` states this explicitly.

## 6. Acceptance criteria

| # | Criterion | Result |
| --- | --- | --- |
| 0 | Every configured profile resolves every required stage | ✅ 5 profiles × 10 stages |
| 1 | All shared and style-specific instructions have explicit, traceable dependencies | ✅ manifest records path, size and SHA-256 |
| 2 | No stage depends on Markdown-heading extraction | ✅ extractors removed; `Descriptor` has no `sections` field |
| 3 | Existing style-specific behavior and source-projection policies unchanged | ✅ 50/50 instruction text preserved; corpus policies asserted |
| 4 | Developmental and reader-review prompts generated from Jinja2 templates | ✅ `prompts/evaluation/*.j2` |
| 5 | All required template variables validated before execution | ✅ strict undefined; `validate_context` reports every missing name |
| 6 | Source content and previous artifacts cannot execute Jinja syntax | ✅ inert strings asserted, including `{{RUN_KEY}}` |
| 7 | Historical outputs, stage artifacts, failure policies and resume behavior compatible | ✅ 606 tests; frozen reference still parses |
| 8 | Prompt changes classified as packaging-only or explicitly approved | ✅ 45 packaging-only, 5 approved, 0 unapproved |
| 9 | All existing Python backend and evaluation tests pass | ✅ 606 passed, 9 skipped |
| 10 | The offline inspection command works for every profile and stage | ✅ recorded example for Synthesis MAX Draft |
| 11 | Byte-equivalence tests distinguish content from packaging | ✅ content compared; packaging changes asserted, not forbidden |

Run them all:

```powershell
python -m pytest
```

## 7. Inspection example — Synthesis MAX Draft

```powershell
python -m digest_system.cli inspect --digest tech-bi-daily \
    --style-profile synthesis-max-v1 --stage draft
```

Writes `system.txt`, `user.txt`, `manifest.json` and `report.md`. The committed example is
`tests/fixtures/phase2b/inspection-example/draft/`, and a test asserts it is byte-reproducible.

`report.md`:

```markdown
# Prompt inspection — synthesis-max-v1 / draft

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.0.0 (experimental)
- Stage: `draft` (executor `llm`)
- Message: system + user

## Templates

- `prompts/stages/draft/system.j2` — 231 units, sha256 `c7c07f7a325a`
- `prompts/shared/preamble.j2` — 463 units, sha256 `8f60794abad6`
- `prompts/stages/draft/user.j2` — 81 units, sha256 `f9c8cd7ef4bd`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `system/contracts/draft.md` — 4386 chars, sha256 `a83ab924e5c3`
- `system/contracts/reader-contract.md` — 3465 chars, sha256 `1e10114ede33`
- `digests/tech-bi-daily.md` — 3784 chars, sha256 `4bc94b96ab1e`

## Style-supplied instructions

- `styles/synthesis-max/modules/01-style-interface.md` — 2850 chars, sha256 `35e389151e7a`
- `styles/synthesis-max/modules/03-synthesis-mode.md` — 3282 chars, sha256 `a6b32685788b`
- `styles/synthesis-max/modules/07-required-structure.md` — 4022 chars, sha256 `8bc77aca136c`
- `styles/synthesis-max/modules/06-length-and-density.md` — 1518 chars, sha256 `72af0519f874`
- `styles/synthesis-max/modules/08-citations.md` — 1576 chars, sha256 `cdeee64d04c3`
- `styles/synthesis-max/modules/09-final-source-catalog.md` — 3170 chars, sha256 `b738bba98859`
- `styles/synthesis-max/modules/10-ending-rules.md` — 313 chars, sha256 `8a33057172b6`
- `styles/synthesis-max/modules/04-writing-character.md` — 2687 chars, sha256 `5688f4f3d85b`
- `system/style-pipelines/synthesis-max/draft.md` — 4896 chars, sha256 `f286a4dc55a2`

## Deliberately omitted style modules

- `styles/synthesis-max/modules/02-writing-reference-profile.md`
- `styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md`
- `styles/synthesis-max/modules/11-quality-control.md`

## Data blocks

- `source_corpus` — 1949 chars
- `approved_frame` — 2190 chars
- `stage_task` — 669 chars
```

`user.txt` — the whole user message:

```text
<source_corpus>
{"digest_id": "tech-bi-daily", ... }

<approved_frame>
{ ... }

<stage_task>
Stage: draft
Digest ID: tech-bi-daily
Selected style: synthesis-max
Output language: English
Purpose: DRAFT: write the editorial body from the approved frame and the evidence the frame selected.
Length target: about 700-1,200 words for the briefing body, excluding the source catalog. Treat this as a binding constraint, not a suggestion.

Return ONLY the complete Markdown artifact. Do not wrap it in a Markdown code fence. ...
</stage_task>
```

A developer can open `prompts/stages/draft/system.j2`, read its declared dependencies, inspect
`synthesis-max-v1.yaml`, and generate exactly what the model will receive — without reading the
executor.

## 8. Test results

```
607 passed, 9 skipped in 109.82s
```

Up from 563 passing before this phase. The 9 skips are the evaluator's opt-in live-judge tests
(`DIGEST_EVAL_RUN_INTEGRATION` unset), unchanged.

New coverage this phase:

* `tests/python/regression/test_phase2b_checklist.py` — 26 tests: the acceptance checklist, the
  classification of every prompt change, and the recorded inspection example.
* `tests/python/integration/test_style_isolation.py` — rewritten for module-based profiles, with
  a sensitivity control and a byte-for-byte style-document reproducibility check.
* `tests/python/unit/test_config_parity.py`, `test_editorial_parity.py`,
  `test_migration_checklist.py`, `test_cli_and_scripts.py` — updated to compare instruction
  content rather than packaging, and to assert that no instruction text was lost.

## 9. Reproducing the evidence

```powershell
# 1. The pre-Jinja2 capture (one-off; requires the historical commit)
git worktree add ../digy-pre2b 8ad4287
copy scripts/capture_pre2b_prompts.py ../digy-pre2b/scripts/
python ../digy-pre2b/scripts/capture_pre2b_prompts.py --output tests/fixtures/phase2b/pre2b-prompts.json
git worktree remove ../digy-pre2b

# 2. The current baseline and the diff
python scripts/capture_prompt_baseline.py --check
python scripts/prompt_diff.py

# 3. The style documents and profiles
python scripts/build_style_docs.py --check
python scripts/export_profiles.py --check

# 4. The full suite
python -m pytest
```

## 10. Outstanding, deliberately not done here

* **The paid historical replays.** Before promoting the Python pipeline to live delivery, the
  historical replays that need a real model must be completed. They belong *after* these offline
  tests, and they are independent of the provider change.
* **The OpenRouter provider migration.** A separate change covering both the editorial executor
  and the evaluator judge. It is not a prompt change, and the interface in
  `digest_system/integrations/models.py` is the seam it will implement.
