# Phase 3A — Reading-instructions implementation and prompt audit

Completion report. Phase 3A implements the canonical four-section reading-instructions contract,
migrates the three existing digest configurations without losing a preference, and establishes a
complete baseline of the resolved prompts before any editorial wording changes.

## 1. Changed and removed files

### Added

| File | Responsibility |
| --- | --- |
| `system/contracts/reading-instructions.md` | Canonical contract: the four sections, their permitted influence, precedence, the effective Reader Brief and stage routing. A specification, never inlined into a prompt. |
| `digest_system/config/reading_instructions.py` | Deterministic Markdown parser and the `ReadingInstructions` model. |
| `digest_system/editorial/prompts/instruction_changes.py` | Loader for the approved-instruction-change record, with glob-aware stage/document matching. |
| `scripts/audit_prompts.py` | Offline audit of every resolved prompt: classification, sizes, estimated tokens, duplicated paragraphs. |
| `docs/architecture/prompt-ownership.md` | Instruction authority and routing through the runtime. |
| `tests/python/unit/test_reading_instructions.py` | Parser, migration, routing and manifest tests. |
| `tests/python/regression/test_phase3a_checklist.py` | The Phase 3A acceptance checklist. |

### Changed

| File | Change |
| --- | --- |
| `digest_system/config/digests.py` | `ResolvedDigest` now carries the parsed `ReadingInstructions` and a body hash; `resolve_digest` parses them once; `read_digest_body` added. |
| `digest_system/config/__init__.py` | Exports the reading-instructions API. |
| `digest_system/editorial/context.py` | `RunContext` holds the instructions and exposes `instructions()`, `reading_sections()`, `reading_instructions_block()`, `reader_brief()`. |
| `digest_system/editorial/stages.py` | Every stage declares its reading-instruction block; the digest-config document is removed from every stage; the two evaluation stages receive the effective Reader Brief via `_reader_contract`. |
| `digest_system/editorial/prompts/assembler.py` | Supports inline-text descriptors (used for the reader-brief augmentation) and resolves reading instructions for offline assembly. |
| `digest_system/editorial/prompts/compose.py` | Adds the `reading_instructions` block tag. |
| `digest_system/editorial/prompts/offline.py` | The offline context exposes the same reading-instruction API. |
| `digest_system/editorial/orchestrator.py` | Parses the instructions before any stage and records the version and per-stage routing in `pipeline.json`. |
| `prompts/stages/{analyze,frame,draft,writer-revision,line-edit,targeted-repair,copy-verify}/user.j2` | Print the `reading_instructions` block in the routed position. |
| `prompts/stages/{analyze,frame,draft,copy-verify,render}/system.j2` | Remove the whole digest-config document reference. |
| `system/contracts/{analyze,frame,draft,render}.md` | "What you receive" now names the reading-instruction sections instead of the whole digest file. |
| `digests/{tech-bi-daily,medium-bi-daily,photography-weekly}.md` | Migrated to the four canonical sections. |
| `tests/fixtures/phase2b/approved-instruction-changes.json` | Records the Phase 3A wording changes, the digest-config removal and the reader-contract augmentation. |
| `tests/fixtures/phase2b/prompt-baseline.json`, `tests/fixtures/phase2b/inspection-example/draft/*` | Regenerated. |
| `scripts/prompt_diff.py`, `scripts/check_prompt_parity.py` | Honor the approval record; compare documents by path. |
| `tests/python/**` (parity, migration, phase2b, cli-and-scripts) | Honor the approval record. |
| `docs/guides/configuring-digests.md` | Rewritten section 3: the four canonical sections, permitted influence, the default reader and the routing table. |

### Removed

* The digest configuration is no longer inlined into any prompt as a single document. It is
  parsed into its operational frontmatter and its four reading-instruction sections, and each
  stage receives only the routed sections.

## 2. The migration: before and after

Each existing instruction is mapped to a canonical section. Nothing was dropped, weakened or
silently reinterpreted.

### `digests/tech-bi-daily.md` (synthesis-max)

| Before | After |
| --- | --- |
| `## Editorial objective` (priority order, learning over recency) | `## Selection` |
| `## Interest profile` (affinity signals, serendipity, "don't let AI crowd out engineering") | `## Selection` |
| `## Selection calibration` (prefer/avoid lists, no-repetition, omission over completeness) | `## Selection` |
| `## Optional editorial signals callouts` (`🔥 TREND`, `🛠 PRACTICAL`, `✍️ WRITE`; ≤4–5) | `## Optional highlights` |
| *(no reader statement existed)* | `## Reader` — added: the generalist default, made explicit because the digest's interest list could otherwise be read as expertise. |
| *(the "unusually valuable to read in full" cue was in the selection list)* | `## Content preferences` — moved here, where "preserve why the original is worth opening" belongs. |

### `digests/medium-bi-daily.md` (curated-discovery)

| Before | After |
| --- | --- |
| `## Core objective` (expected personal value, priority order) | `## Selection` |
| `## Interest profile` | `## Selection` |
| `## Selection calibration` (prefer/downrank, diversity, small-source-set rule) | `## Selection` |
| `## Optional editorial signal callouts` (`🔥 TREND`, `🛠 PRACTICAL`, `✍️ WRITE`; ≤3–4) | `## Optional highlights` |
| *(no reader statement)* | *(none — the digest states no reader, so it runs on the default general reader)* |

### `digests/photography-weekly.md` (curated-discovery)

| Before | After |
| --- | --- |
| `## Editorial objective` (priority order, learning/practice/inspiration) | `## Selection` |
| `## Selection profile` — selection criteria | `## Selection` |
| `## Selection profile` — "preserve source-provided settings… context-dependent starting points" | `## Content preferences` |
| `## Selection profile` — the `Worth opening for:` depth cue | `## Content preferences` |
| `## Practice and opportunity signals` — `📷 TRY THIS` with the Nikon Z DX / 16–50mm / 18–140mm constraint | `## Optional highlights` (the constraint also appears in `Content preferences`, where it governs which practical guidance is achievable) |
| `## Practice and opportunity signals` — `📍 LOCAL & TIMELY`, Montréal relevance | `## Optional highlights` |
| `## Practice and opportunity signals` — `🎓 LEARNING RESOURCE` | `## Optional highlights` |
| `## Selection calibration` (deprioritize gear news; omit routine notifications; promotional sources may still contribute) | `## Selection` |
| *(no reader statement)* | `## Reader` — added: an interest in photography is not advanced expertise, so unfamiliar controls must be explained. |

The Photography digest is the generalizability test: its equipment constraints fit inside
`Content preferences`, its geographical and opportunity preferences inside `Selection` and
`Optional highlights`, and no photography-specific field was added to the contract.

### Instructions that did not fit cleanly

None required omission. Two placements were resolved deliberately:

1. **Photography's equipment constraint** applies to two different decisions: which material is
   *selectable* (practical guidance must be achievable with the reader's kit) and which *callouts*
   are warranted (`📷 TRY THIS` must be achievable with it). It is stated in both sections, because
   the two sections are routed to different stages and both decisions are real.
2. **Tech's "unusually valuable to read in full" cue** was in a selection list but is a
   preservation obligation. It is now a `Content preferences` statement, and the selection list
   retains the *selection* half (prefer material with substantial practical depth).

## 3. Instruction-level differences

`scripts/prompt_diff.py` reports **33 approved instruction changes and 0 unapproved** across 50
profile/stage pairs. `scripts/check_prompt_parity.py` reports **50/50 stage prompts preserve their
instruction text**. Every change is one of:

* **Wording** (`approved`): four stage contracts (`analyze`, `frame`, `draft`, `render`) updated so
  their "What you receive" list names the reading-instruction sections instead of the whole digest
  file. The instruction each stage obeys is unchanged; only the description of its input is.
* **Removal** (`phase3a.removed_documents`): the digest configuration is no longer inlined whole.
  The same text reaches the same stages as a parsed `reading_instructions` block.
* **Augmentation** (`phase3a.augmented_contracts`): the `reader` contract handed to the two
  evaluation stages is the shared reader contract plus the digest's `## Reader` section. The shared
  text is unchanged and still present verbatim.

## 4. Prompt lengths before and after

Measured offline by `scripts/audit_prompts.py` for `synthesis-max-v1` (synthetic context; token
figures are a 4-characters-per-token estimate, and the run record's `usage` is authoritative):

| Stage | Prompt chars | Est. tokens | Instruction documents |
| --- | --- | --- | --- |
| analyze | 48,551 | 12,138 | shared 1, style 3, supporting 2 |
| frame | 52,329 | 13,082 | shared 2, style 7, supporting 1 |
| draft | 54,151 | 13,538 | shared 2, style 9, supporting 1 |
| developmental-review | 20,212 | 5,053 | shared 2, style 2 |
| writer-revision | 17,950 | 4,488 | shared 1, style 2 |
| line-edit | 17,635 | 4,409 | shared 1, style 2, supporting 1 |
| reader-review | 22,822 | 5,706 | shared 2, style 3 |
| targeted-repair | 17,798 | 4,450 | shared 2, style 2 |
| copy-verify | 20,380 | 5,095 | shared 1, style 6 |
| render | 45,236 | 11,309 | rendering 1, shared 2, supporting 1 |

Draft's system message was the audit's focus: it is ~51,000 characters before real-world source
evidence. The audit's role classification and duplicated-paragraph check are the inputs Phase 3B
uses to consolidate; this phase preserves the baseline rather than changing editorial wording.

## 5. Design decisions

* **The parser rejects rather than ignores.** An unknown heading, a duplicate canonical heading, or
  prose outside a section is a preflight error. A preference the runtime cannot route is reported
  before a paid run.
* **Routing is declared once, in one table.** `STAGE_SECTIONS` is the single source of routing
  truth; the contract document and the audit script both read it.
* **The reader brief is a contract augmentation, not a new stage.** The evaluation stages receive
  the shared reader contract plus the digest's `## Reader` section as their `reader` contract, so
  the judge reasons from the same reader the writers used, with no new stage and no competing
  schema.
* **The approval record distinguishes wording, removal and augmentation.** A frozen reference must
  not be edited, and a silent difference is a defect; the record names the kind of change so a
  reviewer can tell a correction from a relocation.
* **Token figures are labelled estimates.** The audit does not pretend to be a tokenizer.

## 6. Test results

* Full suite: **650 passed, 9 skipped** (was 607 passed, 9 skipped). The 43 new tests are the
  parser/migration/routing unit tests and the Phase 3A checklist.
* `scripts/check_prompt_parity.py`: 50/50 preserve instruction text.
* `scripts/prompt_diff.py`: 33 approved, 0 unapproved.
* `scripts/audit_prompts.py`: runs offline for every profile; classifies every supplied document.

## 7. Regressions

None observed. The one duplicate the audit reports is a shared paragraph between
`system/contracts/line-edit.md` and `system/naturalness-contract.md` (136 chars); it is a Phase 3B
consolidation candidate, not a defect this phase introduces.

## 8. Unresolved limitations

* Structural validation cannot guarantee that arbitrary prose is semantically compatible with every
  request. The contract states the permitted influence per section and the runtime surfaces
  identifiable conflicts; a genuinely novel request that overreaches is left to the editorial
  reviewer rather than falsely "validated".
* Callout-type authorization is checked by the callout registry, which is Phase 5 work. Until then,
  an `## Optional highlights` entry naming an unsupported callout is passed to the stages and
  enforced only by the selected style's rendering capabilities.
* The `## Selection` and `## Optional highlights` sections are not yet consulted by the Python
  evaluator's selection audit; that is Phase 4 work.
