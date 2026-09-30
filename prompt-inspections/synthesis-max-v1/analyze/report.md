# Prompt inspection — synthesis-max-v1 / analyze

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.0.0 (active)
- Stage: `analyze` (executor `llm`)
- Message: system + user

## Templates

- `prompts/stages/analyze/system.j2` — 169 units, sha256 `37f13128b259`
- `prompts/shared/preamble.j2` — 463 units, sha256 `8f60794abad6`
- `prompts/stages/analyze/user.j2` — 87 units, sha256 `1a1239d01f06`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `system/contracts/analyze.md` — 6890 chars, sha256 `ebef22008015`
- `system/writing-reasoning-and-source-fidelity.md` — 8403 chars, sha256 `5a41b81c2700`

## Style-supplied instructions

- `styles/synthesis-max/modules/01-style-interface.md` — 2850 chars, sha256 `35e389151e7a`
- `styles/synthesis-max/modules/03-synthesis-mode.md` — 3282 chars, sha256 `a6b32685788b`
- `system/style-pipelines/synthesis-max/analyze.md` — 8692 chars, sha256 `8ebf1f095245`

## Deliberately omitted style modules

- `styles/synthesis-max/modules/02-writing-reference-profile.md`
- `styles/synthesis-max/modules/04-writing-character.md`
- `styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md`
- `styles/synthesis-max/modules/06-length-and-density.md`
- `styles/synthesis-max/modules/07-required-structure.md`
- `styles/synthesis-max/modules/08-citations.md`
- `styles/synthesis-max/modules/09-final-source-catalog.md`
- `styles/synthesis-max/modules/10-ending-rules.md`
- `styles/synthesis-max/modules/11-quality-control.md`

## Data blocks

- `source_corpus` — 2355 chars
- `reading_instructions` — 4005 chars
- `stage_task` — 552 chars

## Sizes

- System: 30574 units
- User: 6997 units

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
