# Prompt inspection — curated-discovery-v1 / analyze

- Digest: `medium-bi-daily`
- Style: `curated-discovery`
- Profile: `curated-discovery-v1` v1.0.0 (active)
- Stage: `analyze` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/analyze/user.j2` — 87 units, sha256 `1a1239d01f06`
- `prompts/shared/task.j2` — 863 units, sha256 `dc71250d7421`

## Instruction documents

- `editorial/stages/analyze.md` — 6748 chars; owner: shared stage contract; sha256 `2226b3936574`
- `editorial/shared/reasoning-fidelity.md` — 8325 chars; owner: shared cross-cutting contract; sha256 `5a41b81c2700`

## Style-supplied instructions

- `styles/curated-discovery/style.yaml` — 546 chars; owner: declarative style constraints; sha256 `7aa6c4c0b7e6`

## Data blocks

- `source_corpus` — 2355 chars; stage-permitted source evidence; source `{"bytes": 2355, "declared_source_numbers": [], "effective_policy": "full", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "full", "source_count": 5, "source_numbers": [1, 2, 3, 4, 5], "warning": null}`
- `reading_instructions` — 4526 chars; prior artifact or digest reading instructions; source `{"path": "digests/medium-bi-daily.md", "sections": ["Selection", "Reader"], "version": "7afce8bdab3412768aaebf25669b29fb890b013c868dfc4a1850b3617380cd00"}`
- `stage_task` — 558 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 16283 units
- User: 7524 units
