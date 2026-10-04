# Prompt inspection — curated-discovery-legacy / line-edit

- Digest: `medium-bi-daily`
- Style: `curated-discovery`
- Profile: `curated-discovery-legacy` v1.1.0 (active)
- Stage: `line-edit` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/line-edit/user.j2` — 117 units, sha256 `70ab0bc67eb5`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `editorial/stages/line-edit.md` — 3955 chars; owner: shared stage contract; sha256 `e8ca371e95b6`
- `editorial/shared/naturalness.md` — 3692 chars; owner: shared cross-cutting contract; sha256 `df0829651a71`

## Style-supplied instructions

- `styles/curated-discovery/stages/line-edit.md` — 1606 chars; owner: style-specific stage specialization; sha256 `ca0e00cb0d72`

## Data blocks

- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/writer-revision/output/writer-revision.md", "provenance": "runner", "stage": "writer-revision"}`
- `reading_instructions` — 920 chars; prior artifact or digest reading instructions; source `{"path": "digests/medium-bi-daily.md", "sections": ["Reader"], "version": "7afce8bdab3412768aaebf25669b29fb890b013c868dfc4a1850b3617380cd00"}`
- `stage_task` — 721 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 10041 units
- User: 2078 units
