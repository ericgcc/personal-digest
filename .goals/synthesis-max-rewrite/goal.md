# Goal: Synthesis MAX Rewrite — Phase 1 (stage-by-stage rebuild in the new architecture)

## Previous Context (provided by the user — treat as authoritative background)

The current committed `prompt-inspections/synthesis-max-v1/` at HEAD be425ece was reviewed
against the source documents that compose them. The recent replays are **B**; this work
produces one optimized **C** directly. There is no reason to resurrect the old A/B/C
prompt-variant machinery.

The review found several concrete problems:

- **Analyze** has ~30.6k chars of system instructions, with the same synthesis/relationship
  ideas spread across `analyze.md`, `synthesis-mode.md`, `synthesis-max/analyze.md`, and
  `writing-reasoning-and-source-fidelity.md`. The last document also contains instructions
  for other styles. More importantly, the Synthesis Analyze procedure still contains
  language derived from the user's personal Tech preferences — e.g. "teaching,
  applicability, ideas, and events" — that must not be a style-level assumption.
- **Frame** is ~49.6k chars. It receives the entire 8.6k `system/style-contract.md`, which
  is overwhelmingly architectural/maintainer documentation. `frame.md` and
  `synthesis-max/frame.md` also substantially overlap on unit design, source limits,
  budget arithmetic, cutting/splitting/demoting, and evidence authority.
- **Draft** is ~51k chars. It receives `synthesis-mode.md`, which literally tells the model
  to interrogate sources, evaluate them, identify relationships, select material, and
  choose editorial structure — decisions that Analyze and Frame have already made. That
  conflicts with Draft's own instruction that Frame is authoritative. It also receives the
  full 14.7k `editorial-base.md` plus Reader Contract, domain-accessibility rules, Writing
  Character, Draft contract, and Synthesis Draft procedure, with substantial semantic
  repetition.
- **Developmental Review, Writer Revision, Line Edit, Reader Review and Targeted Repair**
  all receive the same ~7.9k `synthesis-max/review.md`, even though it contains instructions
  for all five jobs. This is exactly the cross-stage pollution the architecture forbids.
- **Writer Revision** had an authority conflict: the generic contract said it may "reorder,
  expand, cut, split, merge, reframe," while Synthesis's review contract said review stages
  preserve the required structure and must not reopen composition/selection. (Resolved
  policy, now part of the goal: Writer Revision may make substantive structural changes
  required by the Developmental Review — reorder, expand, cut, split, merge, reframe —
  **within the approved evidence set and the edition's fundamental editorial premise**. It
  must not invent sources, facts, or an entirely new synthesis unsupported by Analyze.
  Frame is the best pre-draft plan; Developmental Review may discover that parts of the
  plan failed in prose; Writer Revision may repair those substantive failures. A genuine
  source-selection problem still belongs upstream.)
- **Reader Review** has prompt/schema drift. The Pydantic v4 schema contains
  `explanatory_progression`, `depth_proportion`, per-section `synthesis_quality`, and
  several synthesis-specific flags/lists, while the exact JSON response shape in
  `comparison.j2` omits several of them. Defaults currently mask that mismatch.
- **Copy/Verify** receives six full style modules even though much of their content
  describes editorial decisions it is forbidden to change and many publication checks are
  already deterministic.
- **Render** is ~45.8k chars. About 22.8k comes from the complete
  `system/html-rendering.md`, which contains multi-style architecture, profile
  descriptions, and other material a Synthesis renderer doesn't need. The inspection also
  shows `rendering_values` twice in its data-block manifest.
- The shared `stage_task` repeats output restrictions already present in most stage
  contracts and contains verbose tool prohibitions even though these model calls have no
  such tools.

There is enough evidence for a real prompt rewrite — not simply shortening sentences.

The bigger problem: the prompt/document architecture became too difficult to reason about.
The resolution (already implemented as Architecture Phase 1 and Phase 2 on this branch) is
**composition by whole, purpose-specific files**:

```text
editorial/
  stages/
    analyze.md, frame.md, draft.md, developmental-review.md,
    writer-revision.md, copy-edit.md, reader-review.md,
    targeted-repair.md, publication-verify.md, render.md
  shared/
    reader.md, fidelity.md, quality.md (and the other shared contracts)

styles/
  synthesis-max/
    style.yaml
    stages/
      analyze.md, frame.md, draft.md, developmental-review.md,
      writer-revision.md, copy-edit.md, reader-review.md
  curated-discovery/
    style.yaml, stages/ (rebuilt later — out of scope here)
```

A normal model prompt becomes:

```text
shared stage contract
+ selected style's stage specialization
+ only the shared cross-cutting contract genuinely required here
+ digest-specific runtime data
```

Files are included **whole** — no arbitrary section extraction, no nine tiny modules.
Declarative style properties (composition unit, source limits, budgets, citation type)
live in `styles/<style>/style.yaml` and are consumed by validators and prompt composition;
prose carries only editorial judgment and procedure. Runtime instructions are separated
from documentation by a hard directory boundary (`docs/` can never enter a prompt).

## Objective

This goal is **Goal 2, Phase 1** of the plan in
`docs/changes/Prompt Restructure/plan-goal-2.md`:

1. **Simplify the editorial architecture so it is obvious where every runtime instruction
   comes from.** (Foundation already built in Architecture Phases 1–2; this goal must
   operate entirely within it.)
2. **Rebuild Synthesis MAX stage-by-stage on top of that architecture**, porting the
   editorial behavior deliberately developed in B while eliminating duplication,
   cross-stage instructions, irrelevant context, and personal-preference leakage.

This is an intentional redesign branch. The production implementation exists elsewhere.
Do **not** maintain compatibility layers, legacy profiles, alternate prompt
implementations, or obsolete runtime documents merely for rollback — Git history is the
rollback mechanism. Historical replay outputs and evaluation artifacts may remain as
evidence; historical implementations must not remain executable. `AGENTS.md` is the
governing architectural contract.

## Target End State

The desired editorial flow (already the active stage registry after Architecture
Phase 2):

```text
Analyze
  ↓
Frame
  ↓
Draft
  ↓
Developmental Review
  ↓
Writer Revision
  ↓
Copy Edit
  ↓
Reader Review
  ↓
[Targeted Repair]
  ↓
Publication Verify
  ↓
Render
```

Editorial responsibilities:

```text
ANALYSIS / PLANNING      Analyze, Frame
AUTHORING                Draft
SUBSTANTIVE EDITING      Developmental Review, Writer Revision
DETAILED EDITING         Copy Edit
READER QUALITY CONTROL   Reader Review, Targeted Repair when needed
PUBLICATION QC           Publication Verify (deterministic, code only)
PRESENTATION             Render
```

## Acceptance Criteria

The phase is complete when **every Synthesis MAX model stage** satisfies all of the
following, verified by inspection of the regenerated `prompt-inspections/synthesis-max/`:

- [ ] **AC1 — One clear shared responsibility.** Each stage's shared contract
  (`editorial/stages/<stage>.md`) states exactly that stage's responsibility and nothing
  that belongs to another stage.
- [ ] **AC2 — One clear Synthesis-specific delta.** Each stage's style specialization
  (`styles/synthesis-max/stages/<stage>.md`) contains only what makes Synthesis MAX
  different, with no repetition of the shared contract and no instructions for other
  stages.
- [ ] **AC3 — Only the shared contracts it actually uses.** No stage receives a shared
  contract irrelevant to its responsibility; the routing is explicit and minimal.
- [ ] **AC4 — No instructions for another stage.** No stage prompt contains procedures for
  a different stage (e.g. Draft must not re-select sources or re-group; review stages must
  not rewrite; Copy Edit must not reconsider the article).
- [ ] **AC5 — No personal Tech/Medium/Photography preferences.** No digest-specific value
  categories, priority chains, callout labels, or reader assumptions leak into
  `editorial/` or `styles/synthesis-max/` (per `AGENTS.md` §1; the active digest's
  `## Selection` determines what this reader values at runtime).
- [ ] **AC6 — No maintainer architecture.** No stage prompt receives architecture
  documentation (`system/style-contract.md`-style content), multi-style descriptions, or
  repository/migration material.
- [ ] **AC7 — No obsolete style instructions.** No Concise/Detailed or legacy-profile
  content remains in any active Synthesis MAX prompt path.
- [ ] **AC8 — No contradictory authority boundaries.** Writer Revision's substantive
  authority (evidence-bounded structural change) is stated consistently everywhere it is
  mentioned; Frame is documented as the best pre-draft plan, not an immutable layout;
  Draft does not reopen Analyze/Frame decisions; Publication Verify is code-only.
- [ ] **AC9 — Reader Review schema/prompt synchronized.** The Reader Review evaluation
  prompt's JSON response contract and the Pydantic schema are generated from or verified
  against one authoritative definition; no field exists in the schema that the judge was
  never asked to produce and silently defaults.
- [ ] **AC10 — Stage-specific content is faithful.** The rebuilt stage files preserve the
  editorial behavior worth keeping from B: source-first assessment and relationship
  testing (Analyze); threads vs catalog-only, source roles, honest reduction decisions
  (Frame); explain-before-abstract, distinct source contributions recoverable, terminology
  at point of need (Draft); the 8-category diagnosis approach (Developmental Review);
  evidence-bounded substantive rewrite (Writer Revision); sentence-level copyediting only
  (Copy Edit); first-read comprehension and regression detection (Reader Review); surgical
  one-pass repair (Targeted Repair); presentation-only rendering (Render).
- [ ] **AC11 — Declarative constraints stay in `style.yaml`.** Numeric/structural facts
  (composition unit, source limits, budgets, citation type, catalog mode) are owned by
  `styles/synthesis-max/style.yaml` and are not re-stated as prose in multiple stage
  files beyond what the model needs at point of use.
- [ ] **AC12 — Prompt size decreases naturally.** Irrelevant material is removed; there is
  no arbitrary token target, but the known bloat (Analyze ~30.6k, Frame ~49.6k, Draft
  ~51k, Render ~45.8k with 22.8k of html-rendering architecture) must be measurably
  reduced by removing duplication and irrelevant documents, not by lossy compression of
  editorial substance.
- [ ] **AC13 — Prompt artifacts regenerated and guarded.** `prompt-inspections/` for the
  active Synthesis MAX profile is regenerated and its `--check` guard passes; the prompt
  migration gate reports zero unclassified findings (with the B→C instruction changes
  classified as intentional in the gate's classification record).
- [ ] **AC14 — Quality gates pass.** The full test suite passes, with tests updated to
  assert the new stage contracts instead of protecting superseded file arrangements.

## Scope Boundaries

**In scope:**
- Rewriting the Synthesis MAX stage files (`styles/synthesis-max/stages/`) and the shared
  stage contracts (`editorial/stages/`) where they carry cross-stage or duplicated
  content.
- Adjusting shared-contract routing per stage (only contracts the stage actually uses).
- Moving research explanations and extensive writing theory out of runtime prompts into
  `docs/research/` (or WOPS), keeping a small shared prose-quality floor.
- Fixing the Reader Review prompt/schema drift.
- Trimming Render's input to: final verified Markdown, resolved rendering values,
  style-specific rendering instructions, the shared HTML primitives actually used, canonical
  source information, callout registry, template.
- Regenerating prompt inspections and updating the migration-gate classification record.
- Updating tests that assert the old prompt composition.

**Out of scope:**
- Running C replays, B/C comparison, stage-value analysis, or the Copy Edit keep/remove
  decision (that is Goal 2 Phase 2).
- Rebuilding Curated Discovery against the new architecture.
- Changing the model/provider/reasoning configuration.
- Changing digest definitions (`digests/<digest-id>.md`).
- Changing the stage topology (the ten-stage workflow is fixed by Architecture Phase 2).
- Promoting any digest-specific preference into generic code (`AGENTS.md` §1).

## Applicable Project Conventions

**Quality gate commands** (system Python lacks `yaml`/`jinja2`/`pytest`; use the conda env):
- Full suite: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest`
- Prompt migration gate: `C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\prompt_migration_gate.py`
- Prompt inspection guard: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --check`
- Style docs guard: `C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\build_style_docs.py --check`

**Commit convention:**
- Conventional commits, title ≤72 chars, imperative mood.
- Builder commits: `type(scope): [B] description`; Inspector commits:
  `chore(scope): [I] description`.
- Trailer: `Assisted-by: <PROVIDER>:<MODEL>`.

**Guidelines:**
- `AGENTS.md` — repository-wide architectural and policy invariants (governing contract).
- `.github/copilot-instructions.md` — execution discipline for edits, verification and
  avoiding repeated failed loops.
- `docs/changes/Prompt Restructure/plan-goal-2.md` — the plan this goal implements
  (Synthesis Phase 1 section).

**Rules (from `AGENTS.md`, binding on this goal):**
- §1 Separate system behavior from user preferences; never promote digest-specific values
  into generic runtime logic.
- §2 Reading instructions live in `digests/<digest-id>.md`; the four canonical sections are
  `## Selection`, `## Reader`, `## Content preferences`, `## Optional highlights`.
- §3 Reader expertise is never inferred from topic interest.
- §5 Callouts are an open user-defined vocabulary; the mechanism is generic, the vocabulary
  is digest-defined.
- §6 Shared editorial process, style-specific editorial method; do not duplicate the runner.
- §7 Every instruction has one authoritative owner.
- §9 Use meaningful names, not roadmap phase numbers, for active code/tests/fixtures/docs.
- §10 Historical artifacts are evidence, not active architecture.
- §11 Prefer the smallest originating-stage fix.
- §13 Before committing a general-code change, run the generalization checklist.

**Environment gotchas (from repository memory):**
- Windows/PowerShell: never use `&&`; the workspace is OneDrive-synced; the console is
  cp1252, so scripts call `configure_stdio()`.
- Never bulk-edit files with PowerShell `Set-Content`/`Get-Content -Raw` — it mangles UTF-8.
  Use Python (`read_text`/`write_text`, utf-8) or the edit tools.
- Never leave scratch files in the repository root; clean up immediately.
- Read canonical docs with `newline=""` when byte-exactness matters.
- The frozen `prompt-baseline.json` is the migration gate's reference — do not regenerate
  it casually; B→C instruction changes are classified in the gate's classification record
  (`tests/fixtures/prompt_migration/behavioral-gate.json`).
