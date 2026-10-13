# Prompt inspection — synthesis-max-v1 / writer-revision

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `writer-revision` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/writer-revision/user.j2` — 203 units, sha256 `144c99ae284b`
- `prompts/shared/task.j2` — 595 units, sha256 `97cfa109d8d2`

## Instruction documents

- `editorial/stages/writer-revision.md` — 7691 chars; owner: shared stage contract; sha256 `47b530b6b1f9`
- `editorial/shared/naturalness.md` — 3944 chars; owner: shared cross-cutting contract; sha256 `2a4cdf558760`

## Style-supplied instructions

- `styles/synthesis-max/stages/writer-revision.md` — 1999 chars; owner: style-specific stage specialization; sha256 `e82c87369263`

## Data blocks

- `source_corpus` — 1949 chars; stage-permitted source evidence; source `{"bytes": 1949, "catalog_provenance_numbers": [1, 2, 3, 5], "declared_source_numbers": [1, 2, 3, 5], "effective_policy": "frame-selection", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "frame", "source_count": 4, "source_numbers": [1, 2, 3, 5], "units": [{"disposition": "keep", "retained": true, "selected_source_numbers": [1, 2], "unit_id": "T1"}, {"disposition": "keep", "retained": true, "selected_source_numbers": [3, 5], "unit_id": "T2"}], "warning": null}`
- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/draft/output/draft.md", "provenance": "runner", "stage": "draft"}`
- `approved_frame` — 2190 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/frame/output/frame.json", "provenance": "runner", "stage": "frame"}`
- `writing_operations` — 438 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/developmental-review/output/wops.json", "provenance": "developmental-review", "stage": "developmental-review"}`
- `reading_instructions` — 1030 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Reader"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `stage_task` — 527 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 14436 units
- User: 6688 units
