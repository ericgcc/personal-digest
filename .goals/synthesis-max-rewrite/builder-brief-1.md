# Builder Brief — Iteration 1 (Synthesis MAX Rewrite, Phase 1)

**Goal file:** `.goals/synthesis-max-rewrite/goal.md` (read it once, then execute this brief).
**Your job is EXECUTION ONLY.** Do NOT search the repository. Read only the files named here.
Do NOT run the full test suite until the end; run it once. Never repeat a failing command
without changing something first.

Work the fixes in order. FIX 1–3 are mechanical text deletions; do them first.

---

## FIX 1 — Remove the personal Tech preference leak from Synthesis MAX Analyze

**File:** `styles/synthesis-max/stages/analyze.md`

The section `### Selection is judged against the digest's priorities` contains wording
derived from the user's personal Tech digest. Replace the whole section (from the heading
`### Selection is judged against the digest's priorities` down to, but not including, the
`---` that precedes `## Boundaries`) with this digest-neutral text:

```markdown
### Selection is judged against the digest's priorities

`digests/<digest-id>.md` states this digest's reader interests and its own selection
calibration. Apply *its* priorities; do not substitute a general notion of quality, and do
not assume that a previous run's emphases are this corpus's obligations.

For every promising candidate, record a brief `reader_value_reason` grounded in those
configured preferences, and name the `value_basis` the candidate actually rests on. A
candidate may legitimately rest on novelty, scale, detail volume, recency, or prominence
when the material also carries practical or explanatory value. What must not happen is a
candidate selected *primarily* because it is novel, large, detailed, recent, or prominent:
the recorded `value_basis` is what makes the judgement visible to the editor afterwards.

The converse also holds. Do not exclude material outside the recurring interests when its
practical or explanatory value is exceptional. Serendipity is part of the digest's brief,
and the interests are affinity signals rather than a coverage plan.

The priority order itself lives in `digests/<digest-id>.md`, not in this file. It is that
digest's editorial policy; a different digest using this style may rank its values
differently, and this stage follows whichever digest it is running for.
```

This removes the strings `teaching, applicability, ideas, and events` and
`practical transferability`. After the edit, `grep` the file for `teaching` and
`practical transferability` — both must return nothing.

---

## FIX 2 — Delete the duplicated leading blocks in Analyze, Frame and Draft

Each of these three style stage files begins with a large block copied from another stage's
content, followed by its own `# Synthesis MAX — <Stage>` heading. Delete everything **before**
the `# Synthesis MAX — <Stage>` heading. Keep the heading and everything after it unchanged.

- `styles/synthesis-max/stages/analyze.md` — delete everything before `# Synthesis MAX — Analyze`.
- `styles/synthesis-max/stages/frame.md` — delete everything before `# Synthesis MAX — Frame`.
- `styles/synthesis-max/stages/draft.md` — delete everything before `# Synthesis MAX — Draft`.

The deleted blocks are the duplicated `## Synthesis mode`, `## Required structure`,
`## Length and density`, `## Citations`, `## Final source catalog`, `## Ending rules`,
`## Writing character` and `## Domain accessibility in synthesis` sections. They are already
owned by `styles/synthesis-max/interface.md` and the stage that needs them; the stage file
must not repeat them.

After the edit, each file must begin with its `# Synthesis MAX — <Stage>` heading.

---

## FIX 3 — Remove cross-stage blocks from the five review/revision style files

These files currently carry instructions for other stages. For each file, delete the listed
sections entirely, and add a header line `# Synthesis MAX — <Stage>` as the first line of the
file (these files currently have no H1).

| File | Delete these sections | Keep |
| --- | --- | --- |
| `styles/synthesis-max/stages/developmental-review.md` | `## What these stages must preserve`, `## Boundaries that apply to every stage here`, `## Domain accessibility in synthesis` | `## The invariant that governs this stage`, `## What the developmental review must diagnose`, `## What this stage may and may not do` |
| `styles/synthesis-max/stages/writer-revision.md` | `## Writing character`, `## The invariant that governs this stage`, `## What these stages must preserve`, `## Boundaries that apply to every stage here` | `## What this stage may and may not do` |
| `styles/synthesis-max/stages/copy-edit.md` | `## Writing character`, `## The invariant that governs this stage`, `## What these stages must preserve`, `## Boundaries that apply to every stage here`, `## Domain accessibility in synthesis` | `## What this stage may and may not do` |
| `styles/synthesis-max/stages/reader-review.md` | `## The invariant that governs this stage`, `## What these stages must preserve`, `## Boundaries that apply to every stage here`, `## Domain accessibility in synthesis`, `## Required structure` | `## What this stage may and may not do` |
| `styles/synthesis-max/stages/targeted-repair.md` | `## Writing character`, `## The invariant that governs this stage`, `## What these stages must preserve`, `## Boundaries that apply to every stage here` | `## What this stage may and may not do` |

In each `## What this stage may and may not do` table, keep **only the row for that stage**.
Delete the other stages' rows.

---

## FIX 4 — Give the shared preservation rules one owner

The preservation rules you deleted in FIX 3 are genuinely shared by every review/revision
stage. Create one new shared contract file:

**Create `editorial/shared/preservation.md`** with exactly this content:

```markdown
# Preservation Contract

These rules apply to every review, revision and repair stage. They state what must survive
from the approved draft to publication.

* **Every citation and its claim.** A citation means the referenced source materially
  supports the preceding claim. Do not remove citations, do not add citations, and do not
  move a citation onto a claim its source does not carry.
* **Source contributions the frame assigned.** If a source was selected because it uniquely
  contributes something, that contribution surviving to publication is a requirement, not a
  preference.
* **The distinction between established and inferred.** Where the prose marks an editorial
  inference as an inference, keep it marked.
* **The required structure.** The opening, the numbered threads, their components and the
  source catalogue are the style's shape. Review stages do not restructure.
* **The ending rules.** Nothing follows the source catalogue.
* **Full localization.** All generated reader-facing copy is in the digest's configured
  language. Original source titles are reproduced verbatim and are never translated.

## Boundaries that apply to every stage here

* Do not change the digest's language.
* Do not introduce operational, cost or pipeline data into reader-facing prose.
* Do not weaken the inherited quality floor in `editorial/shared/editorial-base.md` to
  satisfy a style habit, and do not weaken the reader contract to satisfy a style habit.
* Do not resolve a diagnosed problem by adding instructions to every other stage. Identify
  the originating stage and make the smallest change that addresses it.
```

**Then edit `digest_system/editorial/prompts/convention.py`:**

1. Add to `SHARED_CONTRACT_FILES`:
   `"preservation": "editorial/shared/preservation.md",`
2. Change `SHARED_CONTRACTS_BY_STAGE` so the five review/revision stages receive it:
   - `"developmental-review": ("reader", "preservation"),`
   - `"writer-revision": ("preservation",),`
   - `"copy-edit": ("naturalness", "preservation"),`
   - `"reader-review": ("reader", "preservation"),`
   - `"targeted-repair": ("reader", "preservation"),`

**Then edit `tests/python/regression/test_instruction_architecture.py`:**
- Add `"preservation": "editorial/shared/preservation.md",` to `SHARED_CONTRACT_PATHS`.
- Update `EXPECTED_COMPOSITION` for the five stages above to include `"preservation"` in
  their `shared` tuple, in the order given above.

---

## FIX 5 — Synchronize the Reader Review comparison prompt with the schema

**File:** `prompts/evaluation/comparison.j2`

The Pydantic schema (`evaluation/semantic/schema.py`) contains fields the comparison prompt
never asks for, so they silently default. Make the comparison prompt's JSON response shape
match `prompts/evaluation/absolute.j2` exactly for the `after` object.

In the `"dimensions"` object, add after `"reader_orientation": <0-10>`:

```
      "explanatory_progression": <0-10>,
      "depth_proportion": <0-10>
```

(and add a comma after `"reader_orientation": <0-10>`).

In each `section_evaluations` entry, add after `"logical_progression": <0-10>,`:

```
        "synthesis_quality": <0-10>,
```

and after `"takeaway_is_explicit": <true|false>,` add:

```
        "sources_establish_together": <true|false>,
        "relationship_is_explained": <true|false>,
        "abstraction_is_grounded": <true|false>,
        "depth_is_proportionate": <true|false>,
```

and after `"broken_logical_links": [],` add:

```
        "unexplained_relationships": [],
        "unnecessary_aggregation": [],
        "abstraction_before_explanation": [],
        "disproportionate_depth": [],
```

Do not change any other part of the file.

---

## FIX 6 — Remove the duplicate `rendering_values` data block

**File:** `digest_system/editorial/prompts/offline.py`

`stage_extra_blocks` adds a `rendering_values` block for the render stage, but the render
stage declaration in `digest_system/editorial/stages.py` already supplies one. This produces
two `rendering_values` blocks in the render manifest.

Change `stage_extra_blocks` so it returns `{}` for every stage (delete the render branch).
Keep the function and its docstring, but update the docstring to say no stage currently
needs an extra block.

---

## FIX 7 — Trim the shared stage task

**File:** `prompts/shared/task.j2`

The output-restriction sentence repeats what most stage contracts already say, and the tool
prohibitions name tools these model calls do not have. Replace the final `{% if %}` block
(the one starting `{% if stage.executor == "deterministic" %}`) with:

```
{% if stage.executor == "deterministic" %}Return the complete {{ stage.format }} artifact. Do not narrate or explain.{% else %}Return ONLY the complete {{ stage.format }} artifact. Do not wrap it in a Markdown code fence. Do not narrate, explain, or describe the artifact.{% endif %}
```

Leave the rest of the file unchanged.

---

## FIX 8 — Regenerate prompt artifacts and update the migration gate

Run these in order, from the repository root, using the conda interpreter:

1. `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1`
   (regenerate `prompt-inspections/synthesis-max-v1/`).
2. `C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\prompt_migration_gate.py --json`
   — this will report unclassified differences. For each unclassified difference caused by
   FIX 1–7, add a classification entry to
   `tests/fixtures/prompt_migration/behavioral-gate.json` under `classifications`, using
   `"category": "behavioral-change"` for FIX 1, 5, 7 and
   `"category": "deduplication-without-semantic-loss"` for FIX 2, 3, 4, 6, with a one-line
   `justification`. Then update `approved_candidate_sha256` to the value the gate reports.
   Re-run the gate until it reports zero unclassified findings.
3. `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --check`
   — must pass.
4. `C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\build_style_docs.py --check`
   — must pass.

---

## Final gate

Run the full suite once:

`C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest`

Fix only failures caused by FIX 1–8. If a test asserts the old composition (e.g. an exact
`shared` tuple or a duplicated block), update it to the new composition. Do not weaken a test
to make it pass.

---

## Commit

Make **one commit** for the whole iteration. Title:
`refactor(synthesis-max): [B] dedupe stage prompts and fix preference leak`
(≤72 chars). Body: one short paragraph. Trailer: `Assisted-by: Z.ai:GLM 5.3 Flash`.

Then return a concise summary: which fixes completed, the gate results, and any fix you could
not complete.