# Prompt inspection — curated-discovery-legacy / writer-revision

- Digest: `medium-bi-daily`
- Style: `curated-discovery`
- Profile: `curated-discovery-legacy` v1.1.0 (active)
- Stage: `writer-revision` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/writer-revision/user.j2` — 170 units, sha256 `3b3bc7045b73`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `editorial/stages/writer-revision.md` — 3834 chars; owner: shared stage contract; sha256 `a7454e47cba2`

## Style-supplied instructions

- `styles/curated-discovery/stages/writer-revision.md` — 1606 chars; owner: style-specific stage specialization; sha256 `ca0e00cb0d72`

## Data blocks

- `source_corpus` — 1949 chars; stage-permitted source evidence; source `{"bytes": 1949, "catalog_provenance_numbers": [1, 2, 3, 5], "declared_source_numbers": [1, 2, 3, 5], "effective_policy": "frame-selection", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "frame", "source_count": 4, "source_numbers": [1, 2, 3, 5], "units": [{"disposition": "keep", "retained": true, "selected_source_numbers": [1, 2], "unit_id": "T1"}, {"disposition": "keep", "retained": true, "selected_source_numbers": [3, 5], "unit_id": "T2"}], "warning": null}`
- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/draft/output/draft.md", "provenance": "runner", "stage": "draft"}`
- `approved_frame` — 2190 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/frame/output/frame.json", "provenance": "runner", "stage": "frame"}`
- `reading_instructions` — 920 chars; prior artifact or digest reading instructions; source `{"path": "digests/medium-bi-daily.md", "sections": ["Reader"], "version": "7afce8bdab3412768aaebf25669b29fb890b013c868dfc4a1850b3617380cd00"}`
- `stage_task` — 699 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 6136 units
- User: 6267 units
