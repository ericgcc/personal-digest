# Phase 3B prompt variants

This directory holds the temporary prompt variants the design (§3B.3) defines, as data rather
than as code. A variant is a manifest that names the documents each stage receives; the harness
`scripts/prompt_variants.py` measures every variant offline against the live pipeline (variant A).

## The three variants

| Variant | What changes | What it tests |
| --- | --- | --- |
| **A — Baseline** | The live pipeline: the current instruction content with the reading-instructions contract. | Current instruction-following behavior. |
| **B — Structured** | A clearer instruction hierarchy, explicit responsibilities and deduplication. | Whether organization improves adherence. |
| **C — Focused** | The structured variant with unnecessary supporting material removed. | Whether a smaller instruction set performs equally or better. |

Variants B and C are **not yet materialized as manifests**, and that is deliberate. The design
forbids removing approved source evidence or imposing a prompt-length ceiling merely to shrink
prompts, and Phase 3B has already made the two structural improvements that are safe without a
paid comparison:

* the maintainer-facing `system/writing-research-basis.md` was removed from Analyze (it is
  provenance, and `system/workflow.md` already said it need not be loaded);
* the single-owner violation between `system/contracts/line-edit.md` and
  `system/naturalness-contract.md` was consolidated to one owner.

A manifest here may only describe a **selection** of the documents the profile already selects.
It may not remove the shared quality floor (`styles/editorial-base.md`), the reader contract, or
the style's own normative modules: those are requirements, not supporting material.

## How to add a variant

Create `prompts/variants/<name>.json`:

```json
{
  "schema_version": 1,
  "name": "B",
  "label": "Structured — clearer hierarchy and deduplication",
  "note": "Why this variant exists and what it tests.",
  "stages": {
    "draft": ["system/contracts/draft.md", "styles/editorial-base.md", "..."]
  }
}
```

A stage omitted from `stages` keeps the live pipeline's selection for that stage. The harness
reports size, composition and duplication, and the delta against variant A.

## The paid comparison

A full editorial comparison needs paid model calls under a **frozen** model configuration
(design §3B.3 and §10). That workstream is the OpenRouter migration, which must land before the
paid experiments so prompt changes and model changes are never mixed into one experiment. Until
then this directory documents the variants and the offline harness measures them; it does not
claim a winner, because size is not the deciding criterion.
