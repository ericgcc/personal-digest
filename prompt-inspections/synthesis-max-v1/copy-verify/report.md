# Prompt inspection — synthesis-max-v1 / copy-verify

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `copy-verify` (executor `copy-verify`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/copy-verify/user.j2` — 151 units, sha256 `efa5901b9eed`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `editorial/stages/copy-verify.md` — 5362 chars; owner: shared stage contract; sha256 `c4694b00d39b`

## Style-supplied instructions

- `styles/synthesis-max/stages/copy-verify.md` — 10108 chars; owner: style-specific stage specialization; sha256 `418c857f531f`
- `styles/synthesis-max/interface.md` — 2758 chars; owner: style interface declaration; sha256 `be4b146191d8`
- `styles/synthesis-max/style.yaml` — 808 chars; owner: declarative style constraints; sha256 `5d6de26ddacf`

## Data blocks

- `source_corpus` — 2215 chars; stage-permitted source evidence; source `{"bytes": 2215, "declared_source_numbers": [], "effective_policy": "provenance", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "provenance", "source_count": 5, "source_numbers": [1, 2, 3, 4, 5], "warning": null}`
- `reading_instructions` — 760 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Optional highlights"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `deterministic_check_findings` — 34 chars; stage-specific runtime input; source `{"kind": "executor-derived"}`
- `approved_frame_citations` — 65 chars; stage-specific runtime input; source `{"kind": "executor-derived"}`
- `stage_task` — 567 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 19828 units
- User: 1598 units
