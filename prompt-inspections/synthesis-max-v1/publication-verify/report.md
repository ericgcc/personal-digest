# Prompt inspection — synthesis-max-v1 / publication-verify

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `publication-verify` (executor `deterministic`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/publication-verify/user.j2` — 72 units, sha256 `da734c888019`
- `prompts/shared/task.j2` — 595 units, sha256 `97cfa109d8d2`

## Instruction documents

- `editorial/stages/publication-verify.md` — 3081 chars; owner: shared stage contract; sha256 `f3aa1e2d997b`

## Style-supplied instructions

- (none: this stage receives no style-specific document under this profile)

## Data blocks

- `source_corpus` — 2215 chars; stage-permitted source evidence; source `{"bytes": 2215, "declared_source_numbers": [], "effective_policy": "provenance", "kind": "evidence-projection", "missing_source_numbers": [], "recovery": null, "requested_policy": "provenance", "source_count": 5, "source_numbers": [1, 2, 3, 4, 5], "warning": null}`
- `stage_task` — 348 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 3648 units
- User: 349 units
