# Proposal

## Why

The Digest System already retrieves WOPS writing operations for diagnosed problems, but the WOPS **anti-pattern catalogue** (13 structured defect definitions in the WOPS project at `antipatterns/*.yaml`, v0.4.0) is not integrated. Today the pipeline can only react to problems after Developmental Review finds them; it cannot prevent the well-known surface defects of generated prose (manufactured significance, inflated register, synonym cycling, rhetorical formulas, model scaffolding, …) before drafting, cannot detect them with WOPS's own detection signals and false-positive conditions, and cannot verify after revision that a diagnosed anti-pattern was actually repaired. The Naturalness Contract already points at WOPS ("Universal craft principles … now live in **WOPS** as reusable operations and anti-patterns"), but only the operation half is wired up.

## What Changes

- **Draft — prevention.** Draft receives a compact preventive guidance block derived from the WOPS anti-pattern catalogue (summaries + the false-positive conditions that keep legitimate rhetorical devices legal), retrieved/derived through the existing `WopsAdapter`. The complete definitions are never injected; the block is bounded and measured. Selection rotates fairly across runs: stage applicability first, then least-recently-supplied for the same digest and style profile, with a deterministic tie-break — the cap and budget bound prompt size, they never permanently exclude an eligible entry. History comes from existing run artifacts (Draft prompt manifests), with a deterministic fallback when absent.
- **Developmental Review — detection.** The existing developmental-review judge call is extended to also report located, typed anti-pattern findings (canonical WOPS anti-pattern ids, severity, evidence) using WOPS detection signals and false-positive conditions. It may see the prevention-selection record for traceability, but diagnoses the actual prose independently — supplied guidance never suppresses or biases a finding. No new stage, no extra judge call.
- **Repair selection.** `retrieve_writing_operations` in `digest_system/editorial/executor.py` additionally consumes anti-pattern findings: each finding's `repair` operation list is honoured (including empty repair lists, which mean deletion), `overuse_of` relationships are respected, and substantive comprehension problems keep priority over cosmetic style findings.
- **Writer Revision — application.** Writer Revision receives the anti-pattern diagnoses alongside the selected operations in its existing `writing_operations` data block (plus compact prevention context where useful) and repairs them inside the existing call, under the Naturalness Contract and evidence-fidelity rules — repairing diagnosed problems, not mechanically applying every previously supplied rule.
- **Reader Review — verification.** The existing absolute reader-review call additionally checks whether the diagnosed anti-patterns remain and whether Writer Revision introduced meaningful new ones (including defects consistent with overusing supplied operations). It receives the supplied-operation ids and relevant `overuse_of[]` relationships, assesses the revised prose independently first, and reports outcomes without automatically attributing causality. Targeted Repair stays optional and limited to actionable major/critical problems, receiving only relevant unresolved history when it runs.
- **Stage-specific WOPS history.** A lightweight, structured history for the current run — prevention supplied → detected → recommended → supplied → application → outcome — is derived from existing artifacts (prompt manifests, `wops.json`, review JSON, stage records) and delivered stage-scoped. Supply is never interpreted as application or effectiveness; linkage uses canonical ids (`finding_id`, anti-pattern id, operation id). No new artifact family, database, or state subsystem.
- **Observability.** Anti-pattern catalogue availability/version, detected ids with locations and severity, selected repair operation ids with their diagnoses, and Reader Review outcomes are recorded in existing run artifacts (`wops.json`, stage records, review JSON). Model-reported application is distinguished from independently verified improvement.

No new editorial stage, no extra LLM call, no new logging system. Analyze and Frame are untouched. The retired Copy Edit stage stays retired.

## Capabilities

### New Capabilities

- `wops-anti-pattern-integration`: The system's use of the WOPS anti-pattern catalogue across the editorial pipeline — prevention at Draft (with fair rotation across runs), detection at Developmental Review, repair selection for Writer Revision, and verification at Reader Review — including catalogue sourcing from WOPS (never copied locally), bounded prompt overhead, false-positive and `overuse_of` semantics, empty-repair handling, stage-scoped WOPS history within a run, and graceful degradation when WOPS or history is unavailable.

### Modified Capabilities

(none — `openspec list --specs` shows the project has no existing capability specs; this change introduces the first one)

## Impact

- **Code (digest runtime):** `digest_system/editorial/executor.py` (retrieval + anti-pattern plumbing), `digest_system/editorial/stages.py` (draft/writer-revision block declarations), `digest_system/editorial/prompts/offline.py` (synthetic fixtures), `digest_system/integrations/wops.py` (anti-pattern retrieval helpers only if a gap is found — the adapter already exposes `list_anti_patterns` and `get_anti_patterns`).
- **Code (evaluator):** `evaluation/semantic/developmental.py` (anti-pattern findings in the review schema/prompt), `evaluation/semantic/schema.py` + `evaluation/semantic/prompts.py` (reader-review verification fields), `evaluation/adapters/cli.py` (pass-through of the new fields), `evaluation/version.py` (version stamps).
- **Prompts/instructions:** `prompts/evaluation/developmental.j2`, `prompts/evaluation/absolute.j2`, `prompts/evaluation/shared/developmental_discipline.j2`, and a new shared preventive-guidance composition path for Draft. Prompt changes must be classified in `tests/fixtures/prompt_migration/behavioral-gate.json` (the behavioral gate compares complete ordered candidate messages against the frozen baseline and fails on unclassified differences).
- **Tests:** new unit/integration tests for retrieval, prompt composition, detection, repair selection, and verification; existing suites (`tests/python`, `evaluation/tests`) must keep passing.
- **External dependency:** WOPS remains an independent project and the single source of truth; nothing is duplicated into this repository. Unavailability degrades exactly as today.
- **Docs:** `docs/architecture/editorial-pipeline-v2.md` and `docs/architecture/overview.md` describe the integration.
