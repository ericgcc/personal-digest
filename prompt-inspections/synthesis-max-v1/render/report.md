# Prompt inspection — synthesis-max-v1 / render

- Digest: `tech-bi-daily`
- Style: `synthesis-max`
- Profile: `synthesis-max-v1` v2.1.0 (active)
- Stage: `render` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/render/user.j2` — 133 units, sha256 `e1ff6d0effce`
- `prompts/shared/task.j2` — 863 units, sha256 `dc71250d7421`

## Instruction documents

- `editorial/stages/render.md` — 5729 chars; owner: shared stage contract; sha256 `c7469180eb42`
- `rendering/shared.md` — 18317 chars; owner: shared rendering contract; sha256 `fa3cc361874d`
- `templates/synthesis-max-email-v1.html` — 9598 chars; owner: HTML email template; sha256 `dd378e0edbae`

## Style-supplied instructions

- `styles/synthesis-max/rendering.md` — 6900 chars; owner: style rendering profile; sha256 `16593ddb652d`

## Data blocks

- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/publication-verify/output/publication-verify.md", "provenance": "runner", "stage": "publication-verify"}`
- `rendering_values` — 139 chars; prior artifact or digest reading instructions; source `{"path": "source-acquisition/sources.json", "provenance": "delivery", "stage": "source-acquisition"}`
- `source_note_manifest` — 2720 chars; prior artifact or digest reading instructions; source `{"path": "publication-verify/output/final.md", "provenance": "canonical", "stage": "publication-verify"}`
- `callout_registry` — 1236 chars; prior artifact or digest reading instructions; source `{"path": "digests/tech-bi-daily.md", "sections": ["Optional highlights"]}`
- `rendering_values` — 139 chars; stage-specific runtime input; source `{"kind": "executor-derived"}`
- `stage_task` — 533 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 41393 units
- User: 5147 units
