# Prompt inspection — synthesis-max-v1 / frame

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `frame` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/frame/user.j2` — 82 units, sha256 `9ffb1544aae2`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `editorial/stages/frame.md` — 10680 chars; owner: shared stage contract; sha256 `801fa06351d5`
- `editorial/shared/reader.md` — 3357 chars; owner: shared cross-cutting contract; sha256 `c653190e8179`

## Style-supplied instructions

- `styles/synthesis-max/stages/frame.md` — 22670 chars; owner: style-specific stage specialization; sha256 `4c195267086e`
- `styles/synthesis-max/interface.md` — 2758 chars; owner: style interface declaration; sha256 `be4b146191d8`
- `styles/synthesis-max/style.yaml` — 808 chars; owner: declarative style constraints; sha256 `5d6de26ddacf`

## Data blocks

- `reading_instructions` — 1882 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Reader", "Content preferences", "Optional highlights"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `stage_task` — 706 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 41152 units
- User: 2638 units
