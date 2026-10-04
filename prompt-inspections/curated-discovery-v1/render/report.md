# Prompt inspection — curated-discovery-v1 / render

- Digest: `medium-bi-daily`
- Style: `curated-discovery`
- Profile: `curated-discovery-v1` v1.0.0 (active)
- Stage: `render` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/render/user.j2` — 133 units, sha256 `e1ff6d0effce`
- `prompts/shared/task.j2` — 863 units, sha256 `dc71250d7421`

## Instruction documents

- `editorial/stages/render.md` — 5739 chars; owner: shared stage contract; sha256 `46ceae244f4e`
- `rendering/shared.md` — 18317 chars; owner: shared rendering contract; sha256 `fa3cc361874d`
- `templates/curated-discovery-email-v1.html` — 13639 chars; owner: HTML email template; sha256 `2c16be64fd06`

## Style-supplied instructions

- `styles/curated-discovery/rendering.md` — 7061 chars; owner: style rendering profile; sha256 `84adc9234def`

## Data blocks

- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/publication-verify/output/publication-verify.md", "provenance": "runner", "stage": "publication-verify"}`
- `rendering_values` — 139 chars; prior artifact or digest reading instructions; source `{"path": "source-acquisition/sources.json", "provenance": "delivery", "stage": "source-acquisition"}`
- `source_note_manifest` — 2726 chars; prior artifact or digest reading instructions; source `{"path": "publication-verify/output/final.md", "provenance": "canonical", "stage": "publication-verify"}`
- `callout_registry` — 1238 chars; prior artifact or digest reading instructions; source `{"path": "digests/medium-bi-daily.md", "sections": ["Optional highlights"]}`
- `rendering_values` — 139 chars; stage-specific runtime input; source `{"kind": "executor-derived"}`
- `stage_task` — 539 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 45613 units
- User: 5161 units
