# Prompt inspection — synthesis-max-v1 / targeted-repair

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `targeted-repair` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/targeted-repair/user.j2` — 147 units, sha256 `19e31dc361fa`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `editorial/stages/targeted-repair.md` — 2554 chars; owner: shared stage contract; sha256 `10c45823da76`
- `editorial/shared/reader.md` — 3357 chars; owner: shared cross-cutting contract; sha256 `c653190e8179`

## Style-supplied instructions

- `styles/synthesis-max/stages/targeted-repair.md` — 5427 chars; owner: style-specific stage specialization; sha256 `00fa6ccf2a1d`

## Data blocks

- `source_corpus` — 1949 chars; stage-permitted source evidence; source `{"bytes": 1949, "catalog_provenance_numbers": [1, 2, 3, 5], "declared_source_numbers": [1, 2, 3, 5], "effective_policy": "frame-selection", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "frame", "source_count": 4, "source_numbers": [1, 2, 3, 5], "units": [{"disposition": "keep", "retained": true, "selected_source_numbers": [1, 2], "unit_id": "T1"}, {"disposition": "keep", "retained": true, "selected_source_numbers": [3, 5], "unit_id": "T2"}], "warning": null}`
- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/line-edit/output/line-edit.md", "provenance": "runner", "stage": "line-edit"}`
- `reading_instructions` — 1030 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Reader"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `stage_task` — 592 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 12135 units
- User: 4043 units
