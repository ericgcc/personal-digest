# Prompt ownership and instruction routing

Every executable editorial rule has one owner, and a stage receives only the instructions
that can still affect its decision. Runtime instructions and maintainer documentation are
separate trees.

## Authoritative locations

| Concern | Owner |
| --- | --- |
| Stage order, artifacts, corpus policy and validation | `digest_system/editorial/stages.py` |
| What a stage does | `editorial/stages/<stage>.md` |
| Cross-stage reader, fidelity and prose contracts | `editorial/shared/*.md` |
| How a style performs one stage | `styles/<style>/stages/<stage>.md` |
| Shared style identity and composition model | `styles/<style>/interface.md` |
| Declarative composition, budget, evaluation and rendering values | `styles/<style>/style.yaml` |
| Digest-specific reader preferences | Markdown body of `digests/<digest-id>.md` |
| Prompt framing and user-message block order | `prompts/shared/*.j2`, `prompts/stages/<stage>/user.j2` |
| Judge prompt framing | `prompts/evaluation/` |
| Rendering instructions and template | `rendering/shared.md`, `styles/<style>/rendering.md`, `templates/<style>-email-v1.html` |

Files under `docs/`, `system/`, legacy style module directories and profile routing files are
not runtime instruction sources. The loader in
`digest_system/editorial/prompts/instructions.py` enforces that boundary, including resolved
path containment and style scoping.

## System-message composition

```text
SYSTEM: stage contract → style specialization → style interface → shared contracts → constraints
USER: evidence and artifacts → reading instructions → feedback → immediate task
```

`digest_system/editorial/prompts/convention.py` resolves an ordinary stage in this order:

1. `editorial/stages/<stage>.md` — the shared stage contract.
2. `styles/<style>/stages/<stage>.md` — an optional style specialization, present only when
   the style has a genuine stage-specific procedure.
3. `styles/<style>/interface.md` — for stages that need the composition model.
4. Zero to two contracts from `editorial/shared/`.
5. A compact `<style_constraints>` projection from `styles/<style>/style.yaml` for stages that
   make or verify structural decisions.

Every Markdown file is loaded whole. Runtime code does not extract headings or route a list of
small style fragments. The profile selects the style and execution policy; it does not select
editorial instruction documents.

Evaluation stages use the same owners. The adapter receives the stage contract, reader
contract, optional style-stage review procedure and style interface as named contracts.

## User-message composition

The user message contains runtime data, not instruction files:

1. Permitted source evidence or provenance.
2. Prior stage artifacts.
3. The reading-instruction sections routed to this stage.
4. Validator feedback and deterministic findings, when applicable.
5. The immediate task from `prompts/shared/task.j2`.

Each block is delimited and recorded with its source, purpose and size in the prompt manifest.
Article text, artifacts and HTML templates are printed as inert values and are never evaluated
as Jinja source.

## Reading-instruction routing

The digest body is parsed once into four optional sections. Each stage receives only the
sections it can still act on.

| Stage | Sections supplied |
| --- | --- |
| Analyze | `Selection`, `Reader` |
| Frame | `Reader`, `Content preferences`, `Optional highlights` |
| Draft | `Reader`, `Content preferences`, `Optional highlights` |
| Developmental Review | `Reader` |
| Writer Revision | `Reader` |
| Line Edit | `Reader` |
| Reader Review | `Reader` |
| Targeted Repair | `Reader` |
| Copy / Verify | `Optional highlights` |
| Render | none |

The effective Reader Brief is `editorial/shared/reader.md` plus the digest's optional
`## Reader` section. The two evaluation stages receive that same brief.

## Declarative constraints

`styles/<style>/style.yaml` is the single source for values Python and prompts share:
composition limits, body budgets, validator selection, evaluation configuration and rendering
paths. Validators and profile compatibility views derive their values from this file. Only the
model-facing composition, body, citation, catalog and callout values enter
`<style_constraints>`; routing, evaluator identifiers and filesystem paths do not.

Editorial procedure belongs in the stage Markdown files. Those files refer to resolved
constraints instead of copying numeric values into prose.

## Inspection and migration evidence

`python -m digest_system.cli inspect --digest <id> --style-profile <profile> [--stage <stage>]`
uses the production composition path. Its manifest and report show the complete system and user
messages, every instruction owner, every template actually rendered, and the source and purpose
of each runtime data block.

`python scripts/prompt_migration_gate.py` compares the complete ordered candidate prompt set to
the frozen pre-migration baseline. Each reported difference has a category and justification.
The approval record also contains a SHA-256 fingerprint of the complete candidate prompt set,
so additions, removals, replacements, reordering, short lines and constraint changes fail until
the reviewed candidate is deliberately recorded.
