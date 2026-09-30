# Prompt inspection — synthesis-max-v1 / render

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.0.0 (active)
- Stage: `render` (executor `llm`)
- Message: system + user

## Templates

- `prompts/stages/render/system.j2` — 149 units, sha256 `f78d05d2dcec`
- `prompts/shared/preamble.j2` — 463 units, sha256 `8f60794abad6`
- `prompts/stages/render/user.j2` — 133 units, sha256 `e1ff6d0effce`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `system/rendering-synthesis-max.md` — 6949 chars, sha256 `3c0546c2d9c4`
- `templates/synthesis-max-email-v1.html` — 9666 chars, sha256 `dd378e0edbae`
- `system/contracts/render.md` — 5851 chars, sha256 `b09d93fe5e06`
- `system/html-rendering.md` — 22858 chars, sha256 `835bae73aeec`

## Style-supplied instructions

- (none: this stage receives no style-specific document under this profile)

## Deliberately omitted style modules

- (none: this profile supplies every module the stage receives)

## Data blocks

- `previous_stage_artifact` — 332 chars
- `rendering_values` — 139 chars
- `source_note_manifest` — 2678 chars
- `callout_registry` — 1236 chars
- `rendering_values` — 139 chars
- `stage_task` — 533 chars

## Sizes

- System: 45778 units
- User: 5105 units

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
