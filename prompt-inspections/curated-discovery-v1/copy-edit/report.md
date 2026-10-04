# Prompt inspection — curated-discovery-v1 / copy-edit

- Digest: `medium-bi-daily`
- Style: `curated-discovery`
- Profile: `curated-discovery-v1` v1.0.0 (active)
- Stage: `copy-edit` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/copy-edit/user.j2` — 117 units, sha256 `70ab0bc67eb5`
- `prompts/shared/task.j2` — 863 units, sha256 `dc71250d7421`

## Instruction documents

- `editorial/stages/copy-edit.md` — 4594 chars; owner: shared stage contract; sha256 `9226691b95fa`
- `editorial/shared/naturalness.md` — 3692 chars; owner: shared cross-cutting contract; sha256 `2358b8d1d97f`

## Style-supplied instructions

- (none: this stage receives no style-specific document under this profile)

## Data blocks

- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/writer-revision/output/writer-revision.md", "provenance": "runner", "stage": "writer-revision"}`
- `reading_instructions` — 920 chars; prior artifact or digest reading instructions; source `{"path": "digests/medium-bi-daily.md", "sections": ["Reader"], "version": "7afce8bdab3412768aaebf25669b29fb890b013c868dfc4a1850b3617380cd00"}`
- `stage_task` — 885 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 8945 units
- User: 2242 units
