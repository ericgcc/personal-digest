# Synthesis MAX — Analyze

**Stage:** `analyze` · **Style:** `synthesis-max` · **Profile:** `synthesis-max-v1`

This document is operational. It states what *this stage* is responsible for in this style. It does not restate the style's identity or its output requirements: `styles/synthesis-max.md` remains authoritative for both, and `system/contracts/analyze.md` remains authoritative for the stage's role.

---

## What you are given

`system/contracts/analyze.md` states the stage's role and what it receives. This style adds the
selection standard you judge against: its selection model, composition unit and source
relationship (`## Style interface`), its thread-forming tests (`## Synthesis mode`), and the
canonical relationship vocabulary and synthesis test in
`system/writing-reasoning-and-source-fidelity.md`. The digest's reading instructions are the
authority for what this reader values; the style is the authority for how material is combined.

You do **not** receive the style's writing character, its required structure, its citation rules,
its ending rules or a rendering profile. Those govern stages that write and publish a document,
and nothing in them should influence which sources are selected.

---

## Your responsibility in this style

### One call, two passes

Assess the corpus in two distinct passes, in this order. The order is not a formality: a relationship can only be justified by what its members actually establish, so source assessment comes first and is not revised to fit a grouping you have already imagined.

**Pass one — assess the sources.** For every promising source, establish its actual thesis, its strongest evidence or mechanism, what it uniquely contributes that no other source provides, its important caveats or anomalies, and why it is worth the reader's attention at all. Record this per source.

**Pass two — assess the relationships.** For the sources that survived pass one, examine what can be explained *better together than separately*. A shared subject is not a relationship. Two sources covering the same announcement are duplication, and duplication is not synthesis.

Evaluate the whole candidate set before choosing, and record what you decided against. A candidate that was weighed and demoted is useful to Frame; a candidate that never appears is indistinguishable from one that was never examined.

### The cluster record

The proposed groupings go in a top-level array named **`clusters`**. The name is a contract rather than a stylistic choice: Frame reads it to build the shortlist, and the run's validation reads it to check this stage's work. An array under any other name is not read, and an unread array is indistinguishable from an empty one.

Every proposed cluster must carry these fields, with these meanings:

```json
{
  "clusters": [
    {
      "cluster_id": "C1",
      "concrete_subject": "<a subject a reader could recognise without having read the sources>",
      "reader_question": "<the question the combination answers>",
      "source_numbers": ["<two to four corpus source numbers>"],
      "relationship_type": "<one value from the canonical vocabulary, listed below>",
      "source_contributions": [
        { "source_number": "<n>", "unique_contribution": "<what this source adds that no other does>" }
      ],
      "new_understanding": "<what becomes clearer through the combination than through separate summaries>",
      "relationship_counter_test": "<the strongest reason the grouping might not be justified, including whether one member is decorative>",
      "material_to_exclude": ["<material belonging to these sources but not to this cluster>"],
      "selection_decision": "<keep|split|demote|cut>",
      "selection_reason": "<why this decision, given this corpus>",
      "reader_value_reason": "<why this reader values it, in the digest's configured terms>",
      "value_basis": "<the consideration the selection actually rests on>"
    }
  ]
}
```

Rules for these fields:

* **`relationship_type`** must be one value from the canonical vocabulary in `system/writing-reasoning-and-source-fidelity.md` § *Compare sources by relationship, not topic*: `reinforcement`, `extension`, `qualification`, `contradiction`, `complementarity`, `shared_cause_or_consequence`, `independence`. Do not compose new labels. `extension_plus_qualification` is two relationships, and a thread labelled that way cannot be tested against either.
* **`concrete_subject`** must name something a reader could recognise without having read the sources. If it only makes sense as an abstraction, the grouping is not yet justified.
* **`new_understanding`** must say what becomes clearer *through the combination*. "Both sources discuss X" is not an answer. If nothing becomes clearer, the sources have independent value and belong apart.
* **`relationship_counter_test`** must give the strongest reason the grouping might not be justified, including whether one member is merely decorative. A counter-test that nothing could disprove is not a counter-test.
* **`source_contributions`** must cover every number in `source_numbers`, and each entry must be specific to its source. If two entries could be swapped without loss, the sources are not contributing distinctly.
* **`selection_decision`** must be one of `keep`, `split`, `demote`, `cut` — the same vocabulary Frame uses for a unit's `disposition`, so a cluster's decision and a unit's disposition are directly comparable. Do not hedge with `selected_brief_or_catalog`; decide, and say why.
* **`material_to_exclude`** records what belongs to these sources but not to this cluster. Listing nothing is a decision, but it must be a deliberate one.

Record the candidates you weighed and did not keep in `alternatives_considered`, with their decision and reason. That record is what lets Frame and the editor see the selection rather than only its result.

### Selection is judged against the digest's priorities

`digests/<digest-id>.md` states this digest's reader interests and its own selection calibration, including the order in which it values teaching, applicability, ideas, and events. Apply *its* priorities; do not substitute a general notion of quality, and do not assume that a previous run's emphases are this corpus's obligations.

For every promising candidate, record a brief `reader_value_reason` grounded in those configured preferences, and name the `value_basis` the candidate actually rests on. Distinguish **practical transferability** from the considerations that are not by themselves reasons to select:

* **technical novelty** — being new, clever, or technically sophisticated;
* **scale** — being large, fast, or expensive;
* **detail volume** — containing many extractable facts;
* **recency** — being recent;
* **prominence** — coming from a well-known origin.

These are recorded, not forbidden. A candidate may legitimately rest on one of them when the material also carries practical or explanatory value. What must not happen is a candidate selected *primarily* because it is technically sophisticated or because it contains a lot of detail: those are the justifications the digest's own calibration asks you to downrank, and the recorded `value_basis` is what makes the judgement visible to the editor afterwards.

The converse also holds. Do not exclude material outside the recurring interests when its practical or explanatory value is exceptional. Serendipity is part of the digest's brief, and the interests are affinity signals rather than a coverage plan.

The priority order itself lives in `digests/<digest-id>.md`, not in this file. It is that digest's editorial policy; a different digest using this style may rank its values differently, and this stage follows whichever digest it is running for.

---

## Boundaries

* Do not write reader-facing prose. Directions, short titles and structured fields only.
* Do not plan the finished document's shape. Frame decides units, order and depth; Analyze decides what the corpus supports.
* Do not invent a relationship, a fact or a qualification the corpus does not support.
* Do not use a source for a purpose its evidence cannot carry.
* Do not silently drop a source. Every catalog-eligible source receives an assessment and a planned outcome.
* Do not select a group because it gives the digest a substantial thread. A smaller group that can be explained beats a larger one that can only be listed.
* Return only the JSON artifact. No commentary, no code fence, no tools.
