# Proposal

## Why

Curated Discovery is one of two configured editorial styles (`digests/medium-bi-daily.md` and `digests/photography-weekly.md` declare `style: curated-discovery`), but its profile is `unavailable`: `styles/curated-discovery/style.yaml` declares `status: unavailable`, `enforced: []`, and no stage procedures exist under `styles/curated-discovery/stages/`. The runner rejects the profile before creating a run directory, so two of three digests cannot execute. The shared editorial architecture was completed and validated with Synthesis MAX (nine-stage pipeline, convention-based instruction composition, declarative style constraints, WOPS anti-pattern integration, canonical provenance and callouts); porting Curated Discovery onto that architecture is the remaining work of the original roadmap's final phase. The style's editorial identity is preserved and confirmed satisfactory — the task is restructuring its instructions into the established ownership model, not redesigning the style.

## What Changes

- **Style stage procedures.** Create `styles/curated-discovery/stages/` with focused procedures for the seven editorial stages that need them (analyze, frame, draft, developmental-review, writer-revision, reader-review, targeted-repair), derived from the style's preserved identity (`styles/curated-discovery/interface.md`, the recovered original style document in git history) and the historical defect evidence in `medium-bi-daily-20260922T131947Z-15d2`. Publication Verify stays shared and deterministic; Render uses the shared rendering contract plus the style's rendering profile.
- **Declarative constraints.** Complete `styles/curated-discovery/style.yaml`: the enforced validator set, body budget semantics, callout policy, and interface-stage routing — resolved from the style's actual identity, not copied from Synthesis MAX.
- **Rendering profile modernization.** Update `styles/curated-discovery/rendering.md` to reference the current runtime (`rendering/shared.md`, the existing `templates/curated-discovery-email-v1.html`) instead of retired paths (`styles/curated-discovery.md`, `system/html-rendering.md`), preserving the magazine presentation.
- **Activation.** Flip `curated-discovery-v1` from `unavailable` to `active` only after offline acceptance; update `docs/architecture/editorial-pipeline-v2.md` § Styles.
- **Verification.** Curated Discovery editorial-contract tests, cross-style isolation tests, offline prompt inspection for `medium-bi-daily`, prompt-migration gate classification, and a controlled historical replay against the September 22 Medium corpus (paid, separately authorized).
- **No pipeline changes.** The nine-stage workflow, stage table, convention resolver, WOPS integration, evaluation adapter, provenance and callout systems are consumed as-is. Shared Python changes only if a proven incompatibility requires one (smallest general-purpose extension, with a focused regression test).

## Capabilities

### New Capabilities

- `curated-discovery-editorial-style`: The Curated Discovery style's behavior as implemented through the shared editorial pipeline — its value-first selection method, source-independence default, elastic depth model, edition structure (orientation, importance-ordered selections, optional Discoveries, featured treatment, `Worth opening for` cue, source catalog), per-stage procedures, declarative constraints, activation semantics, and the cross-style isolation guarantees that keep Synthesis MAX unaffected.

### Modified Capabilities

(none — `openspec list --specs` shows the project has no archived capability specs yet; the in-flight `wops-anti-pattern-integration` change is unaffected by this work)

## Impact

- **Styles:** `styles/curated-discovery/` — new `stages/` directory (seven files), completed `style.yaml`, modernized `rendering.md`; `interface.md` preserved as the identity contract.
- **Tests:** new `tests/python/regression/test_curated_discovery_editorial_contract.py` (mirroring the Synthesis MAX contract test), cross-style isolation assertions, offline fixture updates where inspection baselines change.
- **Prompts:** new instruction files enter the runtime tree; every addition is classified in `tests/fixtures/prompt_migration/behavioral-gate.json`. The frozen Synthesis MAX baseline is untouched.
- **Docs:** `docs/architecture/editorial-pipeline-v2.md` (§ Styles), `docs/architecture/overview.md` if it names the style's status.
- **Runtime code:** expected none. If the elastic depth model or the Discoveries representation cannot be expressed through existing validators, the smallest general-purpose extension to `digest_system/editorial/validation/editorial.py` is proposed with evidence, and it must not alter Synthesis MAX semantics.
- **Historical artifacts:** `.digest-runs/medium-bi-daily-20260922T131947Z-15d2` and all recorded scores remain immutable evidence.
- **Paid replays:** separately authorized; not an implementation condition.
