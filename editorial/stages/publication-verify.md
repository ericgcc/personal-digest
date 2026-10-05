# Stage Contract — PUBLICATION VERIFY

**Stage:** `publication-verify` · **Artifacts:** `final.md`, `verification.json` · **Kind:** Markdown prose + structured report · **Executor:** deterministic (no model call)

## Role

You are the publication gate. You run code only. You do not call a model, you do not edit prose, and you do not correct anything. You read the revised artifact, run every deterministic publication invariant over it, and publish it forward unchanged beside an auditable report.

The prose that reaches this stage is the prose that is published. This stage exists to prove that the artifact is publication-ready, not to improve it.

## What you verify

The publication requirements, decided mechanically:

1. **Citation integrity.** Every citation marker corresponds to a source number that exists in the reviewed corpus.
2. **Source provenance.** Catalogue titles match the reviewed source titles verbatim. Each named source is the reviewed source it claims to be.
3. **Source catalogue consistency.** The catalogue matches the recorded selection outcomes: one entry per catalogued source, no duplicates, no source appearing under two statuses, and no body citation to a source the catalogue does not account for.
4. **Canonical source identities.** Each source appears once, under one identity. A source-note line must not name the same source twice, and must not link two names to the same article.
5. **Callout authorization and provenance.** A callout is optional. When one is present, its `type` must be a signal the digest's `## Optional highlights` section authorizes, its `source_numbers` must be declared narrative evidence, and the per-unit and per-edition limits must hold.
6. **Required structure.** The style's required sections and components are present.
7. **Markdown correctness.** Headings, links, and emphasis are well formed and will render as intended.
8. **Length sanity.** The body is within the length discipline the style declares, unless the frame declared a catalog-only edition.
9. **Renderability.** The prose contains nothing that would break template mapping: no unresolved placeholder, no operational or internal text, no control characters.
10. **Localization metadata.** The output language is consistent with the digest's configured language.
11. **Final provenance manifest.** The canonical source-note manifest resolves from the revised artifact and the reviewed corpus.
12. **Body-length telemetry.** The body word count is recorded for the run.

## What you may change

Nothing. This stage never edits prose. A failed check is recorded in `verification.json` and surfaced as a run warning; under the current advisory publication policy, Render continues with the unchanged `final.md`.

## Output

Two artifacts:

1. **`final.md`** — the revised prose, published unchanged.
2. **`verification.json`** — one JSON object containing the deterministic checks, their counts, the resolved citations, the catalogue numbers, the body and total word counts, and the catalogue detection method.
