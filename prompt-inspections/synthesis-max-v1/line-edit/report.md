# Prompt inspection — synthesis-max-v1 / line-edit

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.0.0 (active)
- Stage: `line-edit` (executor `llm`)
- Message: system + user

## Templates

- `prompts/stages/line-edit/system.j2` — 154 units, sha256 `29c0ffe06efa`
- `prompts/shared/preamble.j2` — 463 units, sha256 `8f60794abad6`
- `prompts/stages/line-edit/user.j2` — 117 units, sha256 `70ab0bc67eb5`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `system/contracts/line-edit.md` — 4066 chars, sha256 `553b95320159`
- `system/naturalness-contract.md` — 3796 chars, sha256 `c19b2da688a5`

## Style-supplied instructions

- `styles/synthesis-max/modules/04-writing-character.md` — 2687 chars, sha256 `5688f4f3d85b`
- `styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md` — 1819 chars, sha256 `d52388c4ae22`
- `system/style-pipelines/synthesis-max/review.md` — 7945 chars, sha256 `65a6445d9e40`

## Deliberately omitted style modules

- `styles/synthesis-max/modules/01-style-interface.md`
- `styles/synthesis-max/modules/02-writing-reference-profile.md`
- `styles/synthesis-max/modules/03-synthesis-mode.md`
- `styles/synthesis-max/modules/06-length-and-density.md`
- `styles/synthesis-max/modules/07-required-structure.md`
- `styles/synthesis-max/modules/08-citations.md`
- `styles/synthesis-max/modules/09-final-source-catalog.md`
- `styles/synthesis-max/modules/10-ending-rules.md`
- `styles/synthesis-max/modules/11-quality-control.md`

## Data blocks

- `previous_stage_artifact` — 332 chars
- `reading_instructions` — 766 chars
- `stage_task` — 715 chars

## Sizes

- System: 20772 units
- User: 1918 units

## Style modules

- Document: `styles/synthesis-max.md` (generated from `styles/synthesis-max/modules`)
  - `styles/synthesis-max/modules/01-style-interface.md` — ## Style interface
  - `styles/synthesis-max/modules/02-writing-reference-profile.md` — ## Writing reference profile
  - `styles/synthesis-max/modules/03-synthesis-mode.md` — ## Synthesis mode
  - `styles/synthesis-max/modules/04-writing-character.md` — ## Writing character
  - `styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md` — ## Domain accessibility in synthesis
  - `styles/synthesis-max/modules/06-length-and-density.md` — ## Length and density
  - `styles/synthesis-max/modules/07-required-structure.md` — ## Required structure
  - `styles/synthesis-max/modules/08-citations.md` — ## Citations
  - `styles/synthesis-max/modules/09-final-source-catalog.md` — ## Final source catalog
  - `styles/synthesis-max/modules/10-ending-rules.md` — ## Ending rules
  - `styles/synthesis-max/modules/11-quality-control.md` — ## Quality control
