# Prompt inspection — synthesis-max-v1 / analyze

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
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

- `styles/synthesis-max/stages/analyze.md` — 11736 chars; owner: style-specific stage specialization; sha256 `f941d502c82e`
- `styles/synthesis-max/interface.md` — 2758 chars; owner: style interface declaration; sha256 `be4b146191d8`
- `styles/synthesis-max/style.yaml` — 808 chars; owner: declarative style constraints; sha256 `94164faee23e`

## Data blocks

- `source_corpus` — 2355 chars; stage-permitted source evidence; source `{"bytes": 2355, "declared_source_numbers": [], "effective_policy": "full", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "full", "source_count": 5, "source_numbers": [1, 2, 3, 4, 5], "warning": null}`
- `reading_instructions` — 4005 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Selection", "Reader"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `stage_task` — 552 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 31272 units
- User: 6997 units
