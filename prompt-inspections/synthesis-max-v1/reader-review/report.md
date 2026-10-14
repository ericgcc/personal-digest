# Prompt inspection — synthesis-max-v1 / reader-review

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `reader-review` (executor `evaluation`)
- Message: one combined judge prompt

## Templates

- `prompts/evaluation/comparison.j2` — 0 units, sha256 `d1a33b47745b`
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
- `styles/synthesis-max/stages/reader-review.md` — 947 chars; owner: review; sha256 `4c38411b6fb5`
- `editorial/shared/naturalness.md` — 3944 chars; owner: review; sha256 `2a4cdf558760`
- `editorial/stages/reader-review.md` — 2512 chars; owner: role; sha256 `1a65f27ed391`
- `styles/synthesis-max/interface.md` — 2773 chars; owner: style; sha256 `19d3e9cfa543`

## Data blocks

- `evaluation_input` — 24641 chars; combined judge prompt; source `{"contracts": ["reader", "review", "role", "style"], "kind": "evaluation-adapter"}`

## Sizes

- System: 0 units
- User: 0 units
