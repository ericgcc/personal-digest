# Prompt inspection — curated-discovery-legacy / render

- Digest: `medium-bi-daily`
- Style: `curated-discovery`
- Profile: `curated-discovery-legacy` v1.1.0 (active)
- Stage: `render` (executor `llm`)
- Message: system + user

## Templates

- `prompts/shared/preamble.j2` — 465 units, sha256 `8f60794abad6`
- `prompts/stages/render/user.j2` — 133 units, sha256 `e1ff6d0effce`
- `prompts/shared/task.j2` — 992 units, sha256 `d12ba969b789`

## Instruction documents

- `editorial/stages/render.md` — 5740 chars; owner: shared stage contract; sha256 `efa7b4b4ff9b`
- `rendering/shared.md` — 18524 chars; owner: shared rendering contract; sha256 `f46b9afa91a1`
- `templates/curated-discovery-email-v1.html` — 13639 chars; owner: HTML email template; sha256 `2c16be64fd06`

## Style-supplied instructions

- `styles/curated-discovery/rendering.md` — 7061 chars; owner: style rendering profile; sha256 `84adc9234def`

## Data blocks

- `previous_stage_artifact` — 332 chars; prior artifact or digest reading instructions; source `{"path": ".digest-runs/synthetic/copy-verify/output/copy-verify.md", "provenance": "runner", "stage": "copy-verify"}`
- `rendering_values` — 139 chars; prior artifact or digest reading instructions; source `{"path": "source-acquisition/sources.json", "provenance": "delivery", "stage": "source-acquisition"}`
- `source_note_manifest` — 2684 chars; prior artifact or digest reading instructions; source `{"path": "frame/output/frame.json", "provenance": "canonical", "stage": "frame"}`
- `callout_registry` — 1238 chars; prior artifact or digest reading instructions; source `{"path": "digests/medium-bi-daily.md", "sections": ["Optional highlights"]}`
- `rendering_values` — 139 chars; stage-specific runtime input; source `{"kind": "executor-derived"}`
- `stage_task` — 539 chars; immediate task and output contract; source `{"path": "prompts/shared/task.j2"}`

## Sizes

- System: 45821 units
- User: 5119 units
