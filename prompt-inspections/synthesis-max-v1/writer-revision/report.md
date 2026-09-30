# Prompt inspection — synthesis-max-v1 / writer-revision

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.0.0 (active)
- Stage: `writer-revision` (executor `llm`)
- Message: system + user

## Templates

- `prompts/stages/writer-revision/system.j2` — 112 units, sha256 `ee13ea350cc7`
- `prompts/shared/preamble.j2` — 463 units, sha256 `8f60794abad6`
- `prompts/stages/writer-revision/user.j2` — 170 units, sha256 `3b3bc7045b73`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `system/contracts/writer-revision.md` — 3951 chars, sha256 `4bf953a49f9f`

## Style-supplied instructions

- `styles/synthesis-max/modules/04-writing-character.md` — 2687 chars, sha256 `5688f4f3d85b`
- `system/style-pipelines/synthesis-max/review.md` — 7945 chars, sha256 `65a6445d9e40`

## Deliberately omitted style modules

- `styles/synthesis-max/modules/01-style-interface.md`
- `styles/synthesis-max/modules/02-writing-reference-profile.md`
- `styles/synthesis-max/modules/03-synthesis-mode.md`
- `styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md`
- `styles/synthesis-max/modules/06-length-and-density.md`
- `styles/synthesis-max/modules/07-required-structure.md`
- `styles/synthesis-max/modules/08-citations.md`
- `styles/synthesis-max/modules/09-final-source-catalog.md`
- `styles/synthesis-max/modules/10-ending-rules.md`
- `styles/synthesis-max/modules/11-quality-control.md`

## Data blocks

- `source_corpus` — 1949 chars
- `previous_stage_artifact` — 332 chars
- `approved_frame` — 2190 chars
- `reading_instructions` — 1030 chars
- `stage_task` — 693 chars

## Sizes

- System: 15044 units
- User: 6371 units

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
