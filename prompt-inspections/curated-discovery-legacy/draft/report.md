# Prompt inspection — curated-discovery-legacy / draft

- Digest: `medium-bi-daily`
- Style: `curated-discovery`
- Profile: `curated-discovery-legacy` v1.1.0 (active)
- Stage: `draft` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/draft/user.j2` — 103 units, sha256 `81e0da1c5a99`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `editorial/stages/draft.md` — 5215 chars; owner: shared stage contract; sha256 `b58cfb914625`
- `editorial/shared/reader.md` — 3357 chars; owner: shared cross-cutting contract; sha256 `c653190e8179`
- `editorial/shared/editorial-base.md` — 14691 chars; owner: shared cross-cutting contract; sha256 `fa95ec112832`

## Style-supplied instructions

- `styles/curated-discovery/stages/draft.md` — 19044 chars; owner: style-specific stage specialization; sha256 `a0d6053e5118`
- `styles/curated-discovery/interface.md` — 2566 chars; owner: style interface declaration; sha256 `ad54235cddc9`
- `styles/curated-discovery/style.yaml` — 546 chars; owner: declarative style constraints; sha256 `fc5d354d2e95`

## Data blocks

- `source_corpus` — 1949 chars; stage-permitted source evidence; source `{"bytes": 1949, "catalog_provenance_numbers": [1, 2, 3, 5], "declared_source_numbers": [1, 2, 3, 5], "effective_policy": "frame-selection", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "frame", "source_count": 4, "source_numbers": [1, 2, 3, 5], "units": [{"disposition": "keep", "retained": true, "selected_source_numbers": [1, 2], "unit_id": "T1"}, {"disposition": "keep", "retained": true, "selected_source_numbers": [3, 5], "unit_id": "T2"}], "warning": null}`
- `approved_frame` — 2190 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/frame/output/frame.json", "provenance": "runner", "stage": "frame"}`
- `reading_instructions` — 1411 chars; prior artifact or digest reading instructions; source `{"path": "digests/medium-bi-daily.md", "sections": ["Reader", "Optional highlights"], "version": "7afce8bdab3412768aaebf25669b29fb890b013c868dfc4a1850b3617380cd00"}`
- `stage_task` — 675 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 46419 units
- User: 6347 units
