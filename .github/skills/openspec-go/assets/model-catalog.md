# Go / Go Plus catalog and selection reference

Read the maintained [complete model reference](../../../../docs/research/opencode-go-model-reference.md)
for every model's Go and Go Plus 5h/weekly/monthly USD allowances, all pricing
regimes, subjective Builder/Inspector quality tiers, calculated request/token
estimates, privacy constraints, and shared-meter semantics.

The canonical machine-readable catalog is [budget_models.py](../scripts/budget_models.py).
The executable selector is [select_model.py](../scripts/select_model.py).
Read the skill's Usage-aware model selection section before every dispatch.

Kimi K2.6 and Kimi K2.7 Code are excluded across providers. Kimi K3 is eligible
for Inspector after budget and independence checks. No catalog entry overrides
these exclusions. Inspector starts fresh and uses a different family.

Use `opencode_usage.py --catalog --plan go|go-plus` for offline estimates.
Use `select_model.py --plan ... --role ... --available ... --prepare openspec-go`
to bind a runtime selection into an actual scalar-model agent definition.
Private failover metadata or recording a model in status does not bind execution.
