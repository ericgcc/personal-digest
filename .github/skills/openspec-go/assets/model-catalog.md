# Go / Go Plus catalog and selection reference

Read the maintained [complete model reference](../../../../docs/research/opencode-go-model-reference.md)
for every model's Go and Go Plus 5h/weekly/monthly USD allowances, all pricing
regimes, subjective Builder/Inspector quality tiers, calculated request/token
estimates, privacy constraints, and shared-meter semantics.

The canonical machine-readable catalog is [budget_models.py](../scripts/budget_models.py).
The executable selector is [select_model.py](../scripts/select_model.py).
Read the skill's model selection policy section before every `select` action.

Kimi K2.6 and Kimi K2.7 Code are excluded across providers. Kimi K3 is eligible
for Inspector after budget and independence checks. No catalog entry overrides
these exclusions. Inspector starts fresh and uses a different family.

Use `opencode_usage.py --catalog --plan go|go-plus` for offline estimates.
Run `select_model.py --plan ... --role ... --available ...` in the `select`
action (a cheap control chat) and pick the recommended exact host label in the
role chat's model picker. There is no generated agent to bind; the chat model
picker is the binding. Private failover metadata or recording a model in
status does not bind execution.
