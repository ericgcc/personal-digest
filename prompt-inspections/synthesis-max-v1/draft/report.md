# Prompt inspection — synthesis-max-v1 / draft

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `draft` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/draft/user.j2` — 128 units, sha256 `d5c0e93e345a`
- `prompts/shared/task.j2` — 595 units, sha256 `97cfa109d8d2`

## Instruction documents

- `editorial/stages/draft.md` — 5636 chars; owner: shared stage contract; sha256 `c0a9834a85c3`
- `editorial/shared/reader.md` — 3357 chars; owner: shared cross-cutting contract; sha256 `c653190e8179`
- `editorial/shared/editorial-base.md` — 3257 chars; owner: shared cross-cutting contract; sha256 `36674056046c`

## Style-supplied instructions

- `styles/synthesis-max/stages/draft.md` — 2715 chars; owner: style-specific stage specialization; sha256 `15b98157371f`
- `styles/synthesis-max/interface.md` — 2773 chars; owner: style interface declaration; sha256 `19d3e9cfa543`
- `styles/synthesis-max/style.yaml` — 808 chars; owner: declarative style constraints; sha256 `014041abed22`

## Data blocks

- `source_corpus` — 1949 chars; stage-permitted source evidence; source `{"bytes": 1949, "catalog_provenance_numbers": [1, 2, 3, 5], "declared_source_numbers": [1, 2, 3, 5], "effective_policy": "frame-selection", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "frame", "source_count": 4, "source_numbers": [1, 2, 3, 5], "units": [{"disposition": "keep", "retained": true, "selected_source_numbers": [1, 2], "unit_id": "T1"}, {"disposition": "keep", "retained": true, "selected_source_numbers": [3, 5], "unit_id": "T2"}], "warning": null}`
- `approved_frame` — 2190 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/frame/output/frame.json", "provenance": "runner", "stage": "frame"}`
- `reading_instructions` — 1882 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Reader", "Content preferences", "Optional highlights"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `anti_pattern_prevention` — 449 chars; stage-specific runtime input; source `{"kind": "executor-derived"}`
- `stage_task` — 503 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 19538 units
- User: 7150 units
