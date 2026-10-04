# Prompt inspection — synthesis-max-v1 / reader-review

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `reader-review` (executor `evaluation`)
- Message: one combined judge prompt

## Templates

- `prompts/evaluation/comparison.j2` — 0 units, sha256 `1fed12fb14fe`
- `prompts/evaluation/shared/anti_leniency.j2` — 0 units, sha256 `459cfb8e80e6`
- `prompts/evaluation/shared/dimensions.j2` — 0 units, sha256 `f21d9324ceec`
- `prompts/evaluation/shared/issue_taxonomy.j2` — 0 units, sha256 `f2e2901a1b06`
- `prompts/evaluation/shared/critical_failure.j2` — 0 units, sha256 `73d2d4e23c83`
- `prompts/evaluation/shared/citation_note.j2` — 0 units, sha256 `04d4ee07408f`
- `prompts/evaluation/shared/compactness.j2` — 0 units, sha256 `9cdf74863950`

## Instruction documents

- (none)

## Style-supplied instructions

- `editorial/shared/reader.md` — 3357 chars; owner: reader; sha256 `c653190e8179`
- `digests/tech-bi-daily.md` — 739 chars; owner: reader; sha256 `a8169178bea1`
- `styles/synthesis-max/stages/reader-review.md` — 8680 chars; owner: review; sha256 `59ea8f0550df`
- `editorial/stages/reader-review.md` — 3879 chars; owner: role; sha256 `111389fd886d`
- `styles/synthesis-max/interface.md` — 2758 chars; owner: style; sha256 `be4b146191d8`

## Data blocks

- `evaluation_input` — 28901 chars; combined judge prompt; source `{"contracts": ["reader", "review", "role", "style"], "kind": "evaluation-adapter"}`

## Sizes

- System: 0 units
- User: 0 units
