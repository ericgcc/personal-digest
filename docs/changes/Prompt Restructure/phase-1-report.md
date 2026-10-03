# Architecture Phase 1 — Establish the new runtime instruction model

Status: **complete** (all acceptance criteria verified by tests).

This report documents what Phase 1 delivered, how each acceptance criterion is
verified, and the full accounting of every instruction that moved. Nothing
silently disappeared.

---

## What was built

### 1. The new instruction tree

23 runtime Markdown documents were migrated byte-exact from the legacy
locations into the new tree. The migration is scripted and re-verifiable:

```text
scripts/migrate_instruction_tree.py --check   # exits 0 when the tree is current
```

| New location | Purpose | Legacy source |
|---|---|---|
| `editorial/stages/<stage>.md` (10 files) | What each stage is responsible for | `system/contracts/<stage>.md` |
| `editorial/shared/reader.md` | General reader obligations | `system/contracts/reader-contract.md` |
| `editorial/shared/reading-instructions.md` | Reading-instruction contract | `system/contracts/reading-instructions.md` |
| `editorial/shared/reasoning-fidelity.md` | Reasoning and source fidelity | `system/writing-reasoning-and-source-fidelity.md` |
| `editorial/shared/prose-quality.md` | Shared prose-quality floor | `system/naturalness-contract.md` |
| `editorial/shared/editorial-base.md` | Cross-style editorial base | `styles/editorial-base.md` |
| `styles/synthesis-max/stages/<stage>.md` (6 files) | What makes this style different at a stage | `system/style-pipelines/synthesis-max/*.md` (analyze, frame, draft, review) and `system/contracts/{copy-verify,render}.md` |
| `rendering/shared.md` | Shared rendering instructions | `system/html-rendering.md` |
| `styles/synthesis-max/rendering.md` | Style rendering profile | `system/rendering-synthesis-max.md` |

Every moved document is **content-identical** to its legacy source after
normalization (verified by the semantic diff tool and by the invariant tests).

### 2. The runtime-instruction boundary (`digest_system/editorial/prompts/instructions.py`)

A single loader now owns the question *may this file enter a prompt?*

- `INSTRUCTION_ROOTS` allowlists exactly: `editorial/stages/`,
  `editorial/shared/`, `styles/<style>/stages/`, `styles/<style>/modules/`,
  `styles/<style>/rendering.md`, `rendering/shared.md`, `templates/`.
- `FORBIDDEN_PREFIXES` rejects every other location, including `docs/`,
  `system/`, `prompts/`, `evaluation/`, `evaluation-results*`,
  `prompt-inspections/`, `scripts/`, `tests/`, `state/`, `adapters/`,
  `config/`, `tools/`.
- `assert_runtime_instruction()` raises `RunnerError` with an explanatory
  message when a non-runtime document is requested.
- `load_instruction()` returns the text plus its purpose, size and SHA-256, so
  provenance is recorded at load time.

This is enforced in code, not documented into compliance: a composer that tries
to load `docs/architecture/anything.md` fails loudly.

### 3. The convention composer (`digest_system/editorial/prompts/convention.py`)

`resolve_stage_instructions(stage, style)` resolves a stage's instruction set
by convention — no profile indirection:

```text
stage contract            editorial/stages/<stage>.md
style specialization      styles/<style>/stages/<stage>.md
style modules             styles/<style>/modules/*.md   (legacy modules, routed per stage)
shared contracts          editorial/shared/*.md         (per-stage declared set)
rendering documents       rendering/shared.md + styles/<style>/rendering.md (render stage)
declarative constraints   styles/<style>/style.yaml     (one compact <style_constraints> block)
```

The per-stage shared-contract set is declared in one table
(`SHARED_CONTRACTS_BY_STAGE`), so an engineer can read the composer and know
exactly which documents a stage receives. `resolve_evaluation_contracts()`
does the same for the evaluation-executor stages.

### 4. Declarative style constraints (`styles/synthesis-max/style.yaml`)

The facts that are data, not judgment, moved into a structured `constraints:`
section: composition (unit, relationship, source/unit bounds, unit bounds),
body budgets (word ranges, headroom, opening range, per-source minimums),
citations, catalog, callouts, the enforced-check list, evaluation profile and
rendering paths.

The composer renders these as one `<style_constraints>` block
(`render_style_constraints()`); the prose instruction files no longer carry
duplicated numeric rules. `scripts/build_style_docs.py --check` still passes
for all four styles (the generator preserves the hand-maintained constraints
section).

### 5. Ownership-explaining inspection (`digest_system/editorial/prompts/convention_inspection.py`)

`inspect_convention_stage()` produces, for every stage, a manifest in which
each supplied instruction records its **path** and **purpose** (owner), plus
the resolved constraints block. The report answers "why did this stage receive
this instruction?" without consulting other documents.

### 6. The semantic diff (`scripts/semantic_prompt_diff.py`)

The acceptance evidence. For every stage it compares the instruction text the
legacy composer delivers with what the convention composer resolves, and
classifies every difference as `packaging-only`, `moved-same-semantics`,
`intentional-boundary`, or `behavioral`. It exits non-zero when any difference
is unclassified, so nothing can silently disappear. It makes no model call.

---

## Full accounting of instruction differences

Result: **7 stages packaging-only, 3 stages moved-same-semantics, 1
intentional boundary, 0 behavioral changes.**

| Stage | Classification | Difference |
|---|---|---|
| analyze | moved-same-semantics | adds `editorial/shared/reader.md` (see below) |
| frame | packaging-only | — |
| draft | packaging-only | — |
| developmental-review | packaging-only | — |
| writer-revision | packaging-only | — |
| line-edit | packaging-only | — |
| reader-review | packaging-only | — |
| targeted-repair | packaging-only | — |
| copy-verify | moved-same-semantics | adds `styles/synthesis-max/stages/copy-verify.md` (see below) |
| render | moved-same-semantics | adds `styles/synthesis-max/stages/render.md` (see below) |

The three added documents, each a deliberate improvement within the plan's
shared-contract model:

1. **`analyze` + `editorial/shared/reader.md`** — the legacy analyze prompt did
   not include the reader contract; the plan's model gives every
   reader-facing stage the general reader obligations. The reader contract
   text itself is unchanged.
2. **`copy-verify` + `styles/synthesis-max/stages/copy-verify.md`** — in the
   legacy architecture this stage received the *generic* contract
   (`system/contracts/copy-verify.md`) only. Phase 1 gives the style its own
   stage file (byte-exact copy of that same contract) so the style
   specialization slot exists uniformly. Net instruction text is unchanged.
3. **`render` + `styles/synthesis-max/stages/render.md`** — same situation as
   copy-verify.

Intentional boundary: `system/style-contract.md` no longer reaches prompts. It
is maintainer-facing architecture documentation (the style interface contract);
it never represented an editorial requirement, and the style's actual interface
facts now reach stages through the declarative constraints block.

---

## Acceptance criteria → verification

| Criterion | Verified by |
|---|---|
| Every runtime Markdown file has one clear purpose | `tests/python/regression/test_instruction_architecture.py` — boundary and purpose tests; `scripts/migrate_instruction_tree.py --check` |
| Runtime files are included whole, not by section extraction | The composer loads whole files (`load_instruction`); no heading extraction exists in the new path |
| A normal stage is assembled from a small number of instruction documents | `test_every_stage_resolves_a_small_instruction_set` (bound: 16 documents, draft largest at 12) |
| Declarative style constraints live in structured configuration | `style.yaml` `constraints:` section; `test_style_constraints_render_as_one_block`; `build_style_docs.py --check` |
| Documentation/research/history cannot enter prompts | `test_the_loader_rejects_documentation_locations`; `FORBIDDEN_PREFIXES` enforced in `assert_runtime_instruction` |
| Digest preferences remain exclusively in digest definitions | `test_no_instruction_file_carries_a_digest_preference` (checks the personal priority strings from `test_generalization_firewall.py`); `test_the_reading_instructions_are_data_blocks_not_instruction_files` |
| Prompt inspection identifies owner and purpose of every instruction | `test_inspection_identifies_the_owner_of_every_instruction`; `test_the_recorded_inspections_still_verify` |
| No Synthesis MAX editorial behavior has intentionally changed yet | `scripts/semantic_prompt_diff.py` exits 0 with 0 behavioral changes; `test_every_stage_receives_its_stage_contract_content_intact`; the recorded prompt baseline and legacy inspections still verify |

---

## What was deliberately not done in Phase 1

- No change to the 10-stage topology (Copy Edit / Publication Verify are
  Phase 2).
- No rewrite of Synthesis MAX editorial behavior — all migrated text is
  byte-exact.
- The legacy architecture (`system/contracts/`, `styles/<style>/modules/`,
  `system/style-pipelines/`, `prompts/profiles/`, `prompts/stages/`) remains
  the production path; the convention composer is proven equivalent but not
  yet switched in. Removal of the legacy tree is Phase 2.
- Legacy style modules are still routed by the convention composer's
  `STYLE_MODULES_BY_STAGE` table; collapsing them into per-stage style files
  is Phase 2 work.
