# Prompt inspection — synthesis-max-v1 / publication-verify

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `publication-verify` (executor `deterministic`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/publication-verify/user.j2` — 72 units, sha256 `da734c888019`
- `prompts/shared/task.j2` — 863 units, sha256 `dc71250d7421`

## Instruction documents

- `editorial/stages/publication-verify.md` — 3008 chars; owner: shared stage contract; sha256 `2b6b2b5c5c07`

## Style-supplied instructions

- `styles/synthesis-max/interface.md` — 2758 chars; owner: style interface declaration; sha256 `be4b146191d8`
- `styles/synthesis-max/style.yaml` — 808 chars; owner: declarative style constraints; sha256 `94164faee23e`

## Data blocks

- `source_corpus` — 2215 chars; stage-permitted source evidence; source `{"bytes": 2215, "declared_source_numbers": [], "effective_policy": "provenance", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "provenance", "source_count": 5, "source_numbers": [1, 2, 3, 4, 5], "warning": null}`
- `reading_instructions` — 760 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Optional highlights"], "version": "75b7b619c4a1f4549473e2655d469850043600df5e6b2720d30d4ab55f70ceff"}`
- `stage_task` — 448 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 7253 units
- User: 1258 units
