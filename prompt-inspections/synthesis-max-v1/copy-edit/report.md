# Prompt inspection — synthesis-max-v1 / copy-edit

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
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

- `styles/synthesis-max/stages/copy-edit.md` — 7460 chars; owner: style-specific stage specialization; sha256 `436904227b77`

## Data blocks

- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/writer-revision/output/writer-revision.md", "provenance": "runner", "stage": "writer-revision"}`
- `reading_instructions` — 1030 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Reader"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `stage_task` — 879 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 16530 units
- User: 2346 units
