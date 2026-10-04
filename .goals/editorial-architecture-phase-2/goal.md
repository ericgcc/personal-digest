# Goal: Editorial Architecture Phase 2 — Simplify the stages and remove the old architecture

## User Request

> let's start working on goal 1 phase 2, phase 1 is already implemented

(Goal 1 Phase 2 is defined in `docs/changes/Prompt Restructure/plan-goal-1.md`, section
"Architecture Phase 2 — Simplify the editorial stages and remove the old architecture".)

## Refined Goal

Architecture Phase 1 established a new runtime instruction tree (`editorial/stages/`,
`editorial/shared/`, `styles/<style>/stages/`, `rendering/`) with an enforceable boundary
between runtime instructions and documentation, and made the convention composer the
production prompt path. Phase 2 must now simplify the editorial workflow itself and delete
the superseded infrastructure.

Concretely: replace the `line-edit` stage and the editorial half of the LLM `copy-verify`
stage with one `copy-edit` stage; replace LLM `copy-verify` with a deterministic
`publication-verify` stage that never edits prose; keep Writer Revision as a genuine
substantive rewrite bounded by the approved evidence set; make the published structure and
provenance deterministic from the revised artifact rather than the original Frame; remove
the obsolete prompt/profile/module architecture and the out-of-scope Concise/Detailed
implementations; and update the tests to assert architectural invariants instead of
protecting obsolete file arrangements.

The end state is the only active workflow:

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

## Acceptance Criteria

- [ ] **AC1 — Single active workflow.** The stage registry declares exactly these ten stages
  in this order: `analyze`, `frame`, `draft`, `developmental-review`, `writer-revision`,
  `copy-edit`, `reader-review`, `targeted-repair`, `publication-verify`, `render`. No other
  stage name is executable.
- [ ] **AC2 — Copy Edit replaces Line Edit and the editorial part of Copy/Verify.** A
  `copy-edit` stage exists with a shared stage contract (`editorial/stages/copy-edit.md`) and
  a Synthesis MAX specialization (`styles/synthesis-max/stages/copy-edit.md`). Its
  responsibility is detailed copyediting (clarity, grammar, syntax, spelling, punctuation,
  terminology consistency, local redundancy, naturalness, rhythm, awkward phrasing, minor
  local rewording, citation/reference preservation, heading/terminology consistency) and it
  may not significantly restructure the document. `line-edit` no longer exists as a stage.
- [ ] **AC3 — Publication Verify is deterministic.** A `publication-verify` stage exists that
  runs code only (no model call) and produces an auditable structured report. It checks
  publication invariants (valid citation numbers, every cited source exists, no duplicate
  canonical source identity, source/catalog membership, status consistency,
  `Worth reading`/`Selected` disjointness, reading-time presence where required, callout
  authorization and provenance, required top-level components, localization metadata,
  unresolved placeholders, Markdown structural integrity, source-note integrity, final
  provenance manifest, renderability, body-length telemetry). It must not edit prose. A
  failed hard invariant stops Render.
- [ ] **AC4 — Writer Revision retains substantive authority.** The Writer Revision contract
  permits substantive structural change (reorder, expand, cut, split, merge, reframe, rewrite
  a section, change headings, redistribute emphasis) when justified by the developmental
  review, while forbidding: introducing a source outside the approved evidence set, inventing
  facts, inventing a cross-source relationship unsupported by Analyze, changing the
  fundamental style, silently expanding the corpus, or turning a review finding into
  unsupported new content. Frame is documented as the best pre-draft plan, not an immutable
  final layout.
- [ ] **AC5 — Downstream structure follows the revised artifact.** The structure and
  provenance used by later stages and by Render are derived deterministically from the
  revised artifact (final section/unit identifiers, canonical citation/source numbers,
  canonical source metadata, approved callout metadata), not from the original Frame. Source
  identity remains canonical and is never reconstructed by the model. The original Frame
  remains available as planning/audit history.
- [ ] **AC6 — Reader Review compares Writer Revision to Copy Edit.** Reader Review's
  before/after comparison is Writer Revision → Copy Edit, and it asks whether Copy Edit
  preserved comprehension, removed necessary orientation, replaced explanation with
  shorthand, damaged a source relationship, or left the text understandable on first read.
- [ ] **AC7 — Targeted Repair stays optional and surgical.** Targeted Repair runs at most
  once, only when Reader Review detects a material reader-facing problem, is localized,
  evidence-bounded and diagnosis-driven, and does not become a second Writer Revision.
- [ ] **AC8 — Render is presentation-only.** Render consumes verified final prose, rendering
  values, canonical source metadata, the callout registry, the style rendering contract and
  the HTML template, and does not edit prose. The shared rendering instruction contains only
  runtime HTML/email requirements, not multi-style architecture documentation.
- [ ] **AC9 — Superseded architecture deleted.** The obsolete active files are migrated to
  `docs/` (architecture explanation → `docs/architecture/`, writing research →
  `docs/research/`, historical evidence → `docs/history/`) or deleted when they are obsolete
  duplicates. At minimum: `system/style-contract.md`, `system/editorial-pipeline-v2.md`,
  `system/editorial-process.md`, `system/naturalness-migration.md`, `system/style-pipelines/`,
  `styles/*/modules/`, `styles/editorial-base.md`, `system/writing-*.md`, `prompts/profiles/`,
  `prompts/variants/`. No active runtime file is left marked "legacy", "old pipeline",
  "kept for rollback" or similar. No two active representations of the same style remain.
- [ ] **AC10 — Out-of-scope styles removed from the active runtime.** `styles/concise/` and
  `styles/detailed/` (and their rendering profiles/templates) are removed from the active
  runtime. `styles/curated-discovery/` is retained as a style directory, but its legacy
  profile and legacy stage implementations are removed; Curated Discovery will be rebuilt
  fresh against the new architecture later.
- [ ] **AC11 — Tests assert architectural invariants.** Tests whose only purpose was to
  protect obsolete file arrangements are replaced by tests for: every model stage resolves
  one shared stage contract; style specialization is isolated; docs cannot enter runtime
  prompts; declarative constraints have one owner; user preferences cannot leak into
  shared/style logic; Writer Revision retains substantive authority within evidence
  boundaries; Copy Edit cannot restructure substantively; Publication Verify cannot edit
  prose; Render cannot rewrite prose; no active legacy profile/fallback path remains.
- [ ] **AC12 — Prompt artifacts regenerated and guarded.** `prompt-inspections/` is
  regenerated for the active profiles and its `--check` guard passes. The frozen
  `prompt-baseline.json` remains the migration gate's reference and the prompt migration gate
  reports zero unclassified findings.
- [ ] **AC13 — Documentation describes only the final system.** `docs/architecture/` and the
  guides describe the ten-stage workflow and the new instruction ownership; no active
  documentation describes the removed stages as current.
- [ ] **AC14 — Quality gates pass.** The full test suite passes (no failures), and the
  previously failing `tests/python/regression/test_prompt_structure.py::test_the_diff_is_order_independent`
  is replaced by an equivalent invariant test that does not import the deleted
  `scripts/prompt_diff.py`.

## Scope Boundaries

**In scope:**
- The stage topology change: `line-edit` + LLM `copy-verify` → `copy-edit` + deterministic
  `publication-verify`.
- Writer Revision authority and the post-revision structure/provenance representation.
- Reader Review comparison change; Targeted Repair and Render boundaries.
- Deletion/migration of the superseded prompt/profile/module architecture.
- Removal of Concise/Detailed from the active runtime; removal of the Curated Discovery
  legacy profile and legacy stage implementations (style directory retained).
- Test replacement, prompt-inspection regeneration, documentation updates.
- Fixing the one pre-existing test failure caused by the deleted `scripts/prompt_diff.py`.

**Out of scope:**
- Rewriting Synthesis MAX editorial behavior stage-by-stage (that is Goal 2 Phase 1).
- Running C replays, B/C comparison, or the Copy Edit keep/remove decision (Goal 2 Phase 2).
- Rebuilding Curated Discovery against the new architecture.
- Changing the model/provider/reasoning configuration.
- Any change to digest definitions (`digests/<digest-id>.md`) beyond what the stage rename
  strictly requires.
- Promoting any digest-specific preference into generic code (see `AGENTS.md` §1).

## Applicable Project Conventions

**Quality gate command:**
- Full suite: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest`
  (the system Python lacks `yaml`/`jinja2`/`pytest`; the conda env is required).
- Prompt migration gate: `C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\prompt_migration_gate.py`
  (must report zero unclassified findings).
- Prompt inspection guard: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --check`
  (or the equivalent `--check` invocation used by the tests).
- Style docs guard: `C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\build_style_docs.py --check`.

**Commit convention:**
- Conventional commits, title ≤72 chars, imperative mood.
- Builder commits: `type(scope): [B] description`; Inspector commits:
  `chore(scope): [I] description`.
- Trailer: `Assisted-by: <PROVIDER>:<MODEL>`.

**Guidelines:**
- `AGENTS.md` — repository-wide architectural and policy invariants (governing contract).
- `.github/copilot-instructions.md` — execution discipline for edits, verification and
  avoiding repeated failed loops.

**Rules (from `AGENTS.md`, binding on this goal):**
- §1 Separate system behavior from user preferences; never promote digest-specific values
  into generic runtime logic.
- §2 Reading instructions live in `digests/<digest-id>.md`; the four canonical sections are
  `## Selection`, `## Reader`, `## Content preferences`, `## Optional highlights`.
- §3 Reader expertise is never inferred from topic interest.
- §4 Selection preferences are configuration, not platform policy.
- §5 Callouts are an open user-defined vocabulary; the mechanism is generic, the vocabulary
  is digest-defined.
- §6 Shared editorial process, style-specific editorial method; do not duplicate the runner.
- §7 Every instruction has one authoritative owner.
- §9 Use meaningful names, not roadmap phase numbers, for active code/tests/fixtures/docs.
- §10 Historical artifacts are evidence, not active architecture.
- §11 Prefer the smallest originating-stage fix.
- §13 Before committing a general-code change, run the checklist (no digest preference in
  generic code, works for an unknown domain/reader, one authoritative owner, etc.).

**Environment gotchas (from repository memory):**
- Windows/PowerShell: never use `&&`; the workspace is OneDrive-synced; the console is
  cp1252, so scripts call `configure_stdio()`.
- Never bulk-edit files with PowerShell `Set-Content`/`Get-Content -Raw` — it mangles UTF-8.
  Use Python (`read_text`/`write_text`, utf-8) or the edit tools.
- Never leave scratch files in the repository root; clean up immediately.
- Read canonical docs with `newline=""` when byte-exactness matters.
- `js_length()` counts UTF-16 code units, not characters.
