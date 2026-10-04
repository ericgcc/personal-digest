# Prompt inspection — synthesis-max-v1 / line-edit

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
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

- `styles/synthesis-max/stages/line-edit.md` — 7246 chars; owner: style-specific stage specialization; sha256 `e4fe30823ca0`

## Data blocks

- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/writer-revision/output/writer-revision.md", "provenance": "runner", "stage": "writer-revision"}`
- `reading_instructions` — 1030 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Reader"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `stage_task` — 715 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 15677 units
- User: 2182 units
