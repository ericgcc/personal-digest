# Editorial Pipeline

This is the authoritative description of the runnable editorial pipeline. Historical pipeline
records remain auditable, but the runtime executes one workflow only.

## Workflow

```text
Analyze → Frame → Draft → Developmental Review → Writer Revision
        → Reader Review → [Targeted Repair] → Publication Verify → Render
```

| Stage | Artifact | Executor | Responsibility |
| --- | --- | --- | --- |
| Analyze | `analysis.json` | model | Identify evidence-supported editorial opportunities. |
| Frame | `frame.json` | model | Approve the evidence-bounded plan and source-status partition. |
| Draft | `draft.md` | model | Write the first editorial artifact from the approved evidence. Receives a bounded WOPS anti-pattern prevention block (compact guidance, false-positive-aware). |
| Developmental Review | `review.json`, `wops.json` | evaluation | Diagnose the draft; it does not rewrite it. Also reports located, typed anti-pattern findings using WOPS detection signals. |
| Writer Revision | `revision.md` | model | Evidence-bounded substantive revision plus final grammar, clarity, naturalness, rhythm and consistency. Repairs diagnosed anti-patterns via the retrieved operations. |
| Reader Review | `review.json` | evaluation | Absolute first-read assessment of Writer Revision, including whole-edition naturalness. Also verifies anti-pattern outcomes (resolved / partially resolved / still present / new). |
| Targeted Repair | `repair.md` | model | Optionally repair one diagnosed, localized problem. |
| Publication Verify | `final.md`, `verification.json` | deterministic | Audit the final prose without editing it. |
| Render | `email.html` | model | Transform verified prose and canonical rendering data into HTML without rewriting prose. |

Targeted Repair runs at most once and only when Reader Review identifies a material,
evidence-bounded problem. Publication Verify is advisory: failed deterministic checks are recorded
as warnings in `verification.json`, `final.md` is preserved, and Render continues under the current
delivery policy.

## Instruction ownership

Runtime instructions are whole files. The convention resolver composes a stage from the smallest
set of documents that can affect that stage's decision:

| Owner | Location |
| --- | --- |
| Shared stage responsibility | `editorial/stages/<stage>.md` |
| General reader obligations | `editorial/shared/reader.md` |
| Cross-stage editorial quality | `editorial/shared/` |
| Style identity and structure | `styles/<style>/interface.md` |
| Style-specific procedure | `styles/<style>/stages/<stage>.md` |
| Declarative constraints | `styles/<style>/style.yaml` |
| Rendering requirements | `rendering/shared.md` and `styles/<style>/rendering.md` |
| HTML template | `templates/<style>-email-v1.html` |
| Reader preferences | `digests/<digest-id>.md` |

`digest_system/editorial/prompts/` is the only production composition path. It validates every
runtime path before reading it, so documentation, research, history, and traversal paths cannot
enter a model prompt. Prompt inspection records every supplied instruction, its owner, its purpose,
the resolved style constraints, and the runtime data blocks.

Style YAML is the authoritative location for declarative limits and rendering paths. Markdown
contracts state editorial procedure; they do not duplicate numeric constraints.

## Evidence and provenance

Frame is the approved pre-draft plan and source-status partition. Draft and Writer Revision may use
only the approved evidence. Writer Revision may reorder, split, merge, cut, or reframe material
when the developmental diagnosis justifies it; it may not introduce new sources, facts, or
unsupported relationships.

The published structure follows the final prose, not the original Frame. Publication Verify builds
the canonical source-note manifest from final section headings and citations, resolving identity and
metadata from the reviewed corpus. It persists that manifest in `verification.json`; Render consumes
the same manifest rather than reconstructing identities or URLs from model prose.

The Frame remains available as planning and audit history. Its source-status partition is the
canonical mapping for the visible `Selected`, `Worth reading`, and `Reviewed` catalogue outcomes.

## Validation and failure behavior

Writer Revision now owns the former Copy Edit responsibilities and receives the preserved
Naturalness Contract. Reader Review evaluates Writer Revision absolutely and may request
one actionable major/critical repair. No standalone Copy Edit model call or comparison remains.

Publication Verify checks citations, source/catalog membership, source-specific status consistency,
disjoint status sets, reading-time presence, callout authorization and provenance, required
components, Markdown integrity, placeholders, localization metadata, renderability, body-length
telemetry, and the final source-note manifest. It never edits prose.

The exact stage prompt and dependency manifest can be generated or checked offline:

```text
python -m digest_system.cli inspect --digest <digest-id> --style-profile <profile-id> --check
```

## Styles

Synthesis MAX is the active runnable style. Curated Discovery remains declared so existing digest
configuration stays valid, but its status is `unavailable` until it is rebuilt against this
architecture. The runner rejects it before creating a run directory.

Historical prompts, pipelines, and migration evidence live under `docs/history/` and test fixtures.
They are not runtime dependencies.
