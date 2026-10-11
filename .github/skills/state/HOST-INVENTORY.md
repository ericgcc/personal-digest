# Verified host model inventory — how to regenerate

`available-models.json` (this directory, `.github/skills/state/`) is the
**exact host model label list** consumed by `select_model.py --available`.
It is shared runtime state for both the `goal` and `openspec-go` skills
(their scripts resolve `SKILL_STATE` to this same directory). It is runtime
state: regenerate it when models are added/renamed, never hand-edit labels,
never synthesize it from `budget_models.py`'s bare catalog names (a bare
label silently falls back to the session's default chat model — the
2026-10-10 phase2 failure).

## Label format

`<display name> (opencodego)` for OpenCode Go models; `<display name> (openrouter)`
for OpenRouter. The suffix is the vendor id the provider extension registers with
`vscode.lm.registerLanguageModelChatProvider(...)` — it is what makes the host
resolve the endpoint. Verified against the agent-file `model:` completion list.

## Regeneration procedure (three independent sources, cross-checked)

1. **Live API list** — `GET https://opencode.ai/zen/go/v1/models` with
   `Authorization: Bearer $OPEN_CODE_API_KEY` (key lives in the repo `.env`).
   Returns slugs (`deepseek-v4-pro`, `glm-5.3`, `hy4-preview`, …), not labels.
2. **Extension source** — the installed provider extension
   (`onesoftqwq.opencode-go-copilot-provider`) registers vendor id `opencodego`,
   builds each model's `name` from the models.dev catalog display name, and
   filters catalog ids by the live API list. This is what the agent-file
   `model:` completion list shows, suffixed with the vendor id.
3. **models.dev catalog** — `https://models.dev/catalog.json`, provider key
   `opencode-go`, maps slug → display name (`deepseek-v4-pro` →
   `DeepSeek V4 Pro (New)`, `hy4-preview` → `Hy4 preview`, …).

**Intersection of (1) and (3), labeled per (2) = the verified inventory.**
A screenshot of the agent-file completion list confirms the label format
independently.

PowerShell regeneration sketch (never print the key):

```powershell
$key = (Get-Content .env | Where-Object { $_ -match '^OPEN_CODE_API_KEY=' }) -replace '^OPEN_CODE_API_KEY=',''
$api = (Invoke-RestMethod -Uri "https://opencode.ai/zen/go/v1/models" -Headers @{ Authorization = "Bearer $key" }).data | ForEach-Object { $_.id }
$cat = (Invoke-RestMethod -Uri "https://models.dev/catalog.json" -TimeoutSec 30).providers.'opencode-go'.models
$api | ForEach-Object { if ($cat.$_) { "{0} (opencodego)" -f $cat.$_.name } } | ConvertTo-Json | Set-Content available-models.json
```

Then append the OpenRouter entries (currently `DeepSeek V4.1 Flash (openrouter)`,
`GLM-5.3-Flash (openrouter)`) — they resolve through `canonical()`/`provider()`
and are only selectable with `--allow-openrouter` inside the curated
`OPENROUTER_*_PRECEDENCE` lists.

## Reconciliation rule

Selection is a plan; billing is the execution truth. After every dispatch,
reconcile the requested provider against host execution metadata or the
dashboards (opencode.ai/zen/go usage + OpenRouter). `actual: null` after a
dispatch = binding not verified = STOP, not bookkeeping.
