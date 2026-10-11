# Inspector feedback — Iteration 1

Run: `phase1-anti-pattern-catalogue` · Change: `2026-10-10-wops-anti-pattern-integration`
Scope: Phase 1 tasks 1.1–1.7 only · Commit mode: **none** · Date: 2026-10-11
Interpreter: `C:\Users\ericg\.conda\envs\digest-eval\python.exe` (conda env `digest-eval`; system python lacks the deps)

All commands below were run fresh by the Inspector. Nothing in this report rests on the Builder's
claims; each number was re-observed.

---

## A. Task 1.1 — catalogue module (`digest_system/editorial/anti_patterns.py`, new, 202 lines)

Verified by reading the file end to end and by exercising it against the real WOPS checkout.

- `AntiPatternCatalogue` dataclass keeps `available`, `version`, `reason`, `records` (+ `by_id()`).
- `load_catalogue(wops)` calls `list_anti_patterns()` → then `get_anti_patterns(ids)` for the listed
  ids. Confirmed by live execution (see below).
- Degradation: unavailable adapter, `list` failure (`ok: False`), `get` failure, and raised
  exceptions each return `available=False`, `records=[]`, with the adapter's reason (or the call's
  error). Four degradation branches present.
- **No local static anti-pattern definitions**: the module contains only the constants
  `MAX_PREVENTION_ITEMS` and `DEFAULT_PREVENTION_BYTES`; no list of ids, no count.
  A scan of all `digest_system/**/*.py` for the **16 real WOPS ids** and four real names
  (`Empty hedging`, `Manufactured balance`, `Synonym cycling`, `Inflated register`) returned
  **zero hits** (only incidental substring `16` in `anti_patterns.py` and `runtime/artifacts.py`,
  which is not anti-pattern data).
- No direct WOPS Python API import: the module imports only `dataclasses`, `typing`, and
  `..runtime.artifacts`. No `wops.*` import anywhere in the new code.

`tests/python/unit/test_anti_patterns.py` (new, 308 lines) coverage observed:

| Required coverage | Test present |
|---|---|
| load success | `test_load_catalogue_success_with_a_fake_adapter` |
| degradation, adapter unavailable (reason preserved) | `test_load_catalogue_degrades_when_the_adapter_is_unavailable` |
| degradation, list failure | `test_load_catalogue_degrades_when_the_list_call_fails` |
| degradation, fetch failure | `test_load_catalogue_degrades_when_the_fetch_call_fails` |
| dynamic discovery (count from adapter, not a constant) | `test_the_catalogue_count_comes_from_the_adapter_response_not_a_constant` |
| no embedded anti-pattern vocabulary | `test_no_anti_pattern_vocabulary_is_embedded_in_the_module` |
| interface-contract test, skips when no WOPS root | `test_adapter_contract_against_a_real_wops_checkout` (resolves `WOPS_ROOT` from env **or** `.env`, skips when unset/not a directory) |

**Command run:**

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/unit/test_anti_patterns.py -q -o addopts="" -rs
```

**Observed:** `13 passed in 3.46s`, exit 0, **no skips**.

**Live check against the real WOPS checkout** (`WOPS_ROOT` from `.env` =
`C:\Users\ericg\OneDrive\Documents\Cloud\Google Drive\01 - Projects\wops`, exists):

```
adapter available: True version: 0.4.0 reason: None
catalogue available: True count: 16 version: 0.4.0
ids: compulsive-triads, em-dash-overuse, empty-hedging, false-range, formulaic-closers,
     inflated-register, interchangeable-examples, manufactured-balance, manufactured-significance,
     model-scaffolding, outline-in-place-of-explanation, rhetorical-formula, structural-uniformity,
     synonym-cycling, topic-label-headings, unattributed-authority
```

16 entries discovered dynamically, version `0.4.0` read from the adapter — matching the design's
16-entry note. The count is not a constant in code.

## B. Task 1.2 — `prevention_block`

- `MAX_PREVENTION_ITEMS = 5` present and used as the default of `max_items`.
- Byte budget configurable per call (`max_bytes`, default `DEFAULT_PREVENTION_BYTES = 2500`),
  measured with `js_length` — the same UTF-16 measure the prompt manifest records.
- Selection prefers records whose `activities[]` include `drafting`; the rest follow catalogue
  order; the ordering is truncated to `max_items`.
- Whole-entry rendering with false positives in **conditioned** phrasing:
  `"{name} — {summary}"` then one line per false positive: `"It is not a defect when {condition}"`.
- Budget exhaustion omits **whole** entries and records `omitted_count` / `omitted_ids`
  (the first entry is always rendered whole, even alone over budget, so nothing is ever cut).
- Returns `(None, metadata)` when unavailable or empty; metadata always carries
  `selected_ids`, `omitted_count`, `omitted_ids`, `bytes`.

Unit tests verified present for: drafting preference, name+summary+false-positive rendering,
budget-driven whole-entry omission with recorded count, no mid-entry truncation, `None` on
unavailable, `None` on empty.

**Independent behaviour checks I ran myself:**

- Real catalogue, huge budget: selected exactly **5** of the 7 drafting-tagged entries → the item
  cap is enforced; `bytes = 3250` (i.e. it would exceed the default budget, confirming the budget
  path is real).
- Real catalogue, default budget: `selected_ids = ['empty-hedging', 'interchangeable-examples',
  'manufactured-balance']`, `omitted_count = 2`
  (`manufactured-significance`, `outline-in-place-of-explanation`), `bytes = 1949` (< 2500).
- Real catalogue: **no record has an empty `false_positives[]`**, so every rendered line today is
  accompanied by at least one conditioned exception.

## C. Task 1.3 — Draft wiring

Verified in four places plus the template:

- `digest_system/editorial/context.py`: `RunContext.anti_pattern_prevention_block()` returns
  `{"tag": "anti_pattern_prevention", "payload": <text>, "source": {kind, available, version,
  reason, selected_ids, omitted_count, omitted_ids}}` or `None`; it uses the run's adapter
  (`ctx.wops`) and the cached catalogue. Returns `None` when `self.wops is None`.
- `digest_system/editorial/orchestrator.py`: sets `ctx.wops = wops` and
  `ctx.anti_pattern_catalogue = anti_pattern_catalogue` after `load_catalogue(wops)`.
- `digest_system/editorial/stages.py`: Draft's `blocks` gains `ctx.anti_pattern_prevention_block()`.
- `digest_system/editorial/prompts/compose.py`: `"anti_pattern_prevention"` added to `BLOCK_TAGS`.
- `prompts/stages/draft/user.j2`: `{{ [source_corpus, approved_frame, reading_instructions,
  anti_pattern_prevention, validation_feedback, stage_task] | blocks }}`.
- None-handling is already generic in `compose.py` (`if not entry or entry.get("payload") is None:
  continue`), so the absent block simply does not appear. Confirmed empirically by the two
  integration tests.

Integration tests added in `tests/python/integration/test_pipeline_execution.py`:

- `MockWopsWithAntiPatterns` (available mock exposing `list_anti_patterns`/`get_anti_patterns`,
  invented names `Mock Defect A/B`, version `9.9.9-mock`) → `test_draft_receives_the_anti_pattern_prevention_block_when_available`
  asserts `result["degraded"] == []`, `<anti_pattern_prevention>` and `Mock Defect A` in the draft
  user text, and `runtime.wops.anti_patterns == {available: True, version: "9.9.9-mock", reason: None}`.
- Default `MockWops` (unavailable) → `test_draft_omits_the_block_and_completes_when_wops_is_unavailable`
  asserts `<anti_pattern_prevention>` is **absent**, `degraded == []`, and
  `anti_patterns == {available: False, version: None, reason: "mock: WOPS not configured"}`.
- `_run()` gained `wops=kwargs.pop("wops", MockWops())`; every pre-existing test still uses
  `MockWops`, so the existing suite semantics are unchanged.
- Fixture vocabulary is invented (`mock-defect-a/b`, `Mock Defect A`), never real WOPS ids.

**Command run:**

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/integration/test_pipeline_execution.py -q -o addopts="" -rs
```

**Observed:** `19 passed in 14.99s`, exit 0, no skips.

## D. Task 1.4 — offline fixtures

`digest_system/editorial/prompts/offline.py`:

- `SYNTHETIC_ANTI_PATTERNS` added: three invented entries — `Fixture Defect Alpha`
  (`fixture-defect-alpha`), `Fixture Defect Beta`, `Fixture Defect Gamma` (tagged `reviewing`
  rather than `drafting`, so the relevance-ordering path is exercised offline too). No real WOPS
  vocabulary.
- `stage_extra_blocks()` now returns `{"anti_pattern_prevention": text}` for `draft`, computed with
  the **same** `prevention_block()` code path a real run uses (`AntiPatternCatalogue` +
  `prevention_block`), so inspection and baseline capture exercise production selection/rendering
  rather than a hardcoded string. This is the documented `stage_extra_blocks` seam.
- `OfflineContext.anti_pattern_prevention_block()` returns `None` (documented no-op) because the
  offline context has no adapter.

**Command run and re-run:**

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --stage draft
→ synthesis-max-v1/draft: 4 file(s) in prompt-inspections\synthesis-max-v1\draft   (exit 0)
```

`prompt-inspections/synthesis-max-v1/draft/manifest.json` contains:

```json
{ "tag": "anti_pattern_prevention", "bytes": 449,
  "source": { "kind": "executor-derived" },
  "purpose": "stage-specific runtime input" }
```

`bytes = 449 > 0` ✓. Re-running the inspection produced **no further change** to the three
inspection artifacts (deterministic). The rendered block in `user.txt`:

```
<anti_pattern_prevention>
Fixture Defect Alpha — A synthetic surface defect used only for offline prompt inspection.
It is not a defect when the device is used for a genuine contrast
... (Beta, Gamma)
</anti_pattern_prevention>
```

Report shows Draft user message `6646 → 7150` units and the template line
`prompts/stages/draft/user.j2` `103 → 128` units.

## E. Task 1.5 — behavioral gate

**Command run:** `... scripts/prompt_migration_gate.py --json` → **exit 0**.

Observed scalars:

- `unclassified = 0`
- `candidate_sha256 = 18a88f0f9b007e6f3daf0bf517b47097e257eda99303122368b82c853eeee4bb`
- `approved_candidate_sha256 = 18a88f0f9b007e6f3daf0bf517b47097e257eda99303122368b82c853eeee4bb`
- candidate == approved ✓, `ok = true`, `behavioral = 379`.

`tests/fixtures/prompt_migration/behavioral-gate.json` gained exactly two entries, both naming the
block and categorized `behavioral-change`:

- `{"profile":"*","stage":"draft","kind":"added","block":"anti_pattern_prevention","category":"behavioral-change", justification: "WOPS anti-pattern prevention added to Draft…Pha
se 1."}`
- same shape with `"kind": "novel-content"` for the block's lines.

`approved_candidate_sha256` deliberately updated (old `5e9a4532…` → new `18a88f0f…`).

**Baseline untouched:** `git status --short tests/fixtures/prompt_migration/prompt-baseline.json`
prints nothing and `git diff` for it is empty — no baseline regeneration ✓.

**Command run:** `... -m pytest tests/python/regression/test_instruction_architecture.py -q -o addopts=""`
→ **`62 passed in 20.11s`, exit 0** (mutation tests green).

## F. Task 1.6 — pipeline.json catalogue status

`orchestrator.py` writes:

```python
"wops": { **wops.describe(),
          "anti_patterns": {"available": …, "version": …, "reason": …} }
```

Asserted in both new integration tests (available → `True`/`9.9.9-mock`/`None`; unavailable →
`False`/`None`/`"mock: WOPS not configured"`). The catalogue is loaded once per run in the
orchestrator and shared with the context, so the block and the run record cannot disagree.

## G. Task 1.7 — full suite and context measurement

**Full suite (pytest.ini parallelism active, `-n auto`):**

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest -q --tb=no -rs   → exit 0
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest -q --tb=no --junit-xml=…   → exit 0
  tests=870, failures=0, errors=0, skipped=9, time=168.9s
  status counter: {'passed': 861, 'skipped': 9}
```

`pytest --collect-only -q` → `870 tests collected`.

**No new skips.** All 9 skips are pre-existing, in the untouched
`evaluation/tests/test_integration_smoke.py` (reason `DIGEST_EVAL_RUN_INTEGRATION is not set to 1`,
one per line: 127, 138, 144, 154, 168, 180, 198, 212, 223). Because the total skip set contains no
anti-pattern test, the new interface-contract test **ran live and passed**, not skipped.

**Context measurement** (`... scripts/measure_context.py`):

| profile | total | style-owned |
|---|---|---|
| curated-discovery-v1 | 122722 | 21529 |
| synthesis-max-v1 | 135845 | 38469 |

Draft growth: the draft user message grew `6646 → 7150` units (**+504**) in the committed
inspection report; the block itself is **449** bytes (the remaining ~55 units are the
`<anti_pattern_prevention>` wrapper tags and separators). Pre-change figures read from
`git show HEAD:prompt-inspections/synthesis-max-v1/draft/report.md` (`User: 6646 units`).

## H. Spec conformance spot-checks

Requirement 1 — *Anti-pattern catalogue is sourced from WOPS*: satisfied. Only the adapter wrappers
`list_anti_patterns`/`get_anti_patterns` are used; the WOPS Python API is never imported; no static
definitions; no hardcoded count/id list; `WOPS_ROOT` is consumed as a local filesystem path; the
run record states availability and version.

Requirement 2 — *Draft receives bounded preventive anti-pattern guidance*: satisfied. Each rendered
entry is whole (`name — summary` + false positives), bounded by `MAX_PREVENTION_ITEMS = 5` and a
2500-unit byte budget with whole-entry omission and a recorded count; the block's size is recorded
in the prompt manifest (449 bytes); **no complete detection-signal lists, examples, or provenance**
appear in the rendered block (verified in `user.txt` and in the live render); selection uses
`activities[]`; unavailability omits the block.

Requirement 3 — *Preventive guidance preserves legitimate devices*: satisfied. `_render_entry`
emits every false positive as `"It is not a defect when …"`; no line prohibits a device outright.
I also verified against the live catalogue that every one of the 16 records carries at least one
false-positive condition, so no unconditioned line can be rendered with today's catalogue.

Scope boundaries:

- No Analyze or Frame changes; no new stage, executor, or judge call. The only stage touched is
  Draft (`blocks`) plus the generic composition seam.
- No WOPS project edits (outside this repository anyway).
- No direct `wops.*` Python API import in the new module.
- No baseline regeneration (verified empty diff on `prompt-baseline.json`).
- Generalization firewall: no real WOPS anti-pattern vocabulary in `digest_system/` (verified by
  scanning all `digest_system/**/*.py` for all 16 real ids + 4 real names → zero hits). Fixture names
  are invented (`Fixture Defect Alpha/Beta/Gamma`, `Mock Defect A/B`) — **not** real ids such as
  `manufactured-significance`.

---

## Findings

**F1 (non-blocking, coverage gap) — the item cap itself is not directly unit-tested.**
`tests/python/unit/test_anti_patterns.py` covers budget-driven omission ("a synthetic catalogue
larger than the cap omits whole entries with a recorded count" is realized via `max_bytes=120`), but
no test asserts that a catalogue larger than `MAX_PREVENTION_ITEMS` yields at most 5 entries. I
verified the behaviour myself against the real catalogue (7 drafting entries → exactly 5 selected),
so the implementation is correct; only the regression lock is missing. Suggest adding one test:
8 synthetic records, huge budget, assert `len(selected_ids) == MAX_PREVENTION_ITEMS == 5`.

**F2 (non-blocking, coverage gap) — the two `except Exception` branches in `load_catalogue` are
untested.** The tests cover the `ok: False` paths but not an adapter that *raises*. The code path is
correct (it degrades with `list_anti_patterns failed: …` / `get_anti_patterns failed: …`); a `FakeWops`
variant that raises from each method would lock it in.

**F3 (non-blocking, minor D1 deviation) — the byte budget is configurable in code, not via runtime
configuration.** D1 says "a configurable byte budget (default ~2,500 chars, **overridable via runtime
configuration**)". `max_bytes` is a call parameter with the constant default; `RunContext.anti_pattern_prevention_block()`
calls `prevention_block(catalogue)` with no override, and neither `system/runtime.json` nor the run
config carries an anti-pattern budget key (I checked `system/runtime.json`: only `wops_root`,
`wops_python`, `wops_timeout_ms`). The budget is therefore overridable by a caller but not by
configuration. No task or scenario requirement depends on it, so this is a note for Phase 2/3 rather
than a defect. Recommendation: either read a config key in `RunContext` or soften the design wording.

**F4 (non-blocking, cosmetic) — rendered false-positive lines read awkwardly.**
WOPS false-positive strings are capitalized sentences, so the render produces
`"It is not a defect when The hedge names a real condition, as when a result holds…"`.
Correct but clunky; lowercasing the first character of the condition (or dropping the leading "The")
would read better. Content semantics are unaffected.

**F5 (non-blocking, doc nit) — self-contradictory comment in `context.py`.** The new fields carry the
comment "Not a declared dataclass field with a real default because the run context is built once…",
but they *are* declared dataclass fields with `None` defaults (`wops: Any = None`,
`anti_pattern_catalogue: Any = None`). Harmless; suggest rewording.

**F6 (non-blocking, efficiency nit) — lazy load is not cached.**
`RunContext.anti_pattern_prevention_block()` loads the catalogue locally when
`self.anti_pattern_catalogue` is None but does not assign it back, so a context without the
orchestrator-provided cache would re-invoke the WOPS CLI per Draft attempt (validation retries).
The orchestrator always sets the cache today, so this has no current effect.

**F7 (informational, scope note) — `.gitignore` is modified outside the change's technical scope.**
The run touched `.gitignore`: `..openspec-go/` → `.openspec-go/` (a pre-existing path typo fix). It is
needed so run state is not carried as untracked files, and it touches no product behaviour, but it is
not part of tasks 1.1–1.7; flag it before commit so it is a conscious inclusion.

## I. Cross-check of the Builder's evidence (`validation-1.md`)

| Builder claim | Inspector observation | Match |
|---|---|---|
| Unit tests 13 passed | 13 passed in 3.46s | ✓ |
| Integration tests 19 passed | 19 passed in 14.99s | ✓ |
| Interface-contract test ran live, passed, not skipped | Ran live (real WOPS root present) and passed; skip set contains only the 9 evaluation smoke tests | ✓ |
| Gate exit 0, `unclassified: 0`, both sha256 = `18a88f0f…eee4bb` | Identical values observed first-hand | ✓ |
| `test_instruction_architecture.py` 62 passed | 62 passed in 20.11s | ✓ |
| Manifest block `anti_pattern_prevention`, 449 bytes | Same block, same 449 bytes | ✓ |
| `measure_context.py`: curated 122722/21529, synthesis-max-v1 135845/38469 | Identical | ✓ |
| Draft growth "449 units" | The block is 449 bytes; the draft **user message** grew 6646 → 7150 = **+504** units (449 block + ~55 wrapper/separator units) | slight understatement (see below) |
| Full suite exit 0, no new skips | 870 tests, 861 passed, 9 pre-existing skips, 0 failures/errors, exit 0 | ✓ (Builder recorded only ≤ counts for two files; I recorded the whole suite) |
| Commit mode none, no commits | HEAD `7e51ed5`, all changes uncommitted | ✓ |

Discrepancy to note: the Builder's "Draft context growth equals … **449 units** in the draft user
message" conflates the block's byte size with the user-message growth. The block is 449 bytes; the
Draft user message grew by 504 units because the `<anti_pattern_prevention>` wrapper tags and blank
separators are additional. Not a defect, but the phase report should quote 504 for message growth and
449 for the block.

## J. Worktree state

```
git status --short
 M .gitignore
 M digest_system/editorial/context.py
 M digest_system/editorial/orchestrator.py
 M digest_system/editorial/prompts/compose.py
 M digest_system/editorial/prompts/offline.py
 M digest_system/editorial/stages.py
 M openspec/changes/2026-10-10-wops-anti-pattern-integration/tasks.md
 M prompt-inspections/synthesis-max-v1/draft/manifest.json
 M prompt-inspections/synthesis-max-v1/draft/report.md
 M prompt-inspections/synthesis-max-v1/draft/user.txt
 M prompts/stages/draft/user.j2
 M tests/fixtures/prompt_migration/behavioral-gate.json
 M tests/python/integration/test_pipeline_execution.py
?? digest_system/editorial/anti_patterns.py
?? tests/python/unit/test_anti_patterns.py

git log --oneline -3
7e51ed5 (HEAD -> feat/rework-programmatic-workflow, origin/feat/rework-programmatic-workflow) update anti-pattern function names
3361bba update specs
290588b update specs
```

- HEAD is still `7e51ed5` — **no new commits**, as required by commit mode `none` ✓.
- All changes uncommitted ✓.
- Diff is confined to Phase 1 scope: 6 product files (`anti_patterns.py` new, `context.py`,
  `orchestrator.py`, `compose.py`, `offline.py`, `stages.py`), one template (`draft/user.j2`), one
  gate fixture (`behavioral-gate.json`; baseline **not** touched), two test files, the regenerated
  draft inspection artifacts (expected — they are the deliverable of 1.4), and `tasks.md`
  (checkbox toggles for 1.1–1.7 only; no other line changed). Nothing under `evaluation/`, no
  Analyze/Frame stage changes, no version stamps, no new stage/executor/judge call.
- The only file outside the technical change free-body is `.gitignore` (F7).

## Verdict

Every Phase 1 task (1.1–1.7) is implemented and independently verified; the three Phase 1
requirements are met; the full suite is green (870 tests, 861 passed, 9 pre-existing skips), the
behavioral gate exits 0 with `unclassified: 0` and a matching deliberate fingerprint, the baseline is
unmodified, no commits were made, and no generalization-firewall violation exists. The seven findings
above are non-blocking (two test-coverage gaps that Phase 2 should not leave open, one minor D1
deviation about runtime configurability, and cosmetic/scope notes).
