# Style Contract

A style defines the editorial product; the platform defines the workflow; a digest defines what
one reader wants. These layers are independent.

Each style lives under `styles/<style>/`:

| File | Owner |
| --- | --- |
| `interface.md` | The style's identity, structure, and reader-facing product. |
| `stages/<stage>.md` | A genuine style-specific procedure for that stage, when needed. |
| `style.yaml` | Declarative constraints, profile status, evaluation configuration, and rendering paths. |
| `rendering.md` | Style-specific presentation requirements. |

The convention resolver supplies the shared stage contract, the appropriate shared editorial
contracts, the style interface where it can affect a decision, an optional stage specialization,
and resolved constraints. It includes complete files and never routes Markdown headings or legacy
modules.

Styles do not define a pipeline. Every runnable style uses the shared ten-stage workflow. A style
whose implementation has not been rebuilt declares `status: unavailable`; it remains valid digest
configuration but the runner rejects it before creating a run.

Rules have one owner. Numeric bounds, source limits, body budgets, catalog requirements, and
rendering paths live in `style.yaml`; Markdown documents explain editorial method without repeating
those values. Digest-specific preferences remain in the four canonical sections of
`digests/<digest-id>.md` and never become style or platform policy.
