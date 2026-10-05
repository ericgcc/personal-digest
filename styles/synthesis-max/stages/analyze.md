# Synthesis MAX — Analyze

## Source-first assessment

Assess the corpus in two passes, in this order.

**Pass one — assess each source.** Establish its actual thesis, strongest evidence or
mechanism, meaningful qualifications or anomalies, unique contribution, and why it may
deserve this reader's attention. Do this before proposing any grouping. Do not revise a
source assessment merely to make a later grouping look stronger.

**Pass two — test relationships.** Among the sources that survive the first pass, ask what
becomes easier to understand together than separately. A shared topic is not enough, and
two reports of the same event may be duplication rather than synthesis. Classify the
relationship with the supplied canonical vocabulary and keep sources independent when no
honest relationship improves understanding.

For every proposed thread, test all of the following:

1. **Concrete subject:** What recognizable topic, question, mechanism, development, or
   tension do the sources illuminate?
2. **Distinct contribution:** What does each source add that the others do not?
3. **New understanding:** What becomes clearer through the combination?
4. **Evidence boundary:** Which parts are source claims and which part is editorial
   inference?
5. **Counter-test:** What is the strongest reason this grouping may be unjustified,
   including a decorative member or a material caveat?
6. **Semantic distance:** Does the relationship remain concrete, or does it appear only
   after translating distant material into a slogan, metaphor, or broad principle?

If the combined idea is no more informative than separate summaries, do not synthesize it.

## Cluster record

Record proposed groupings in a top-level `clusters` array. Each cluster must contain:

```json
{
  "cluster_id": "C1",
  "concrete_subject": "<a subject understandable without reading the sources>",
  "reader_question": "<the question the combination answers>",
  "source_numbers": ["<contributing source numbers within the resolved bounds>"],
  "relationship_type": "<one canonical relationship value>",
  "source_contributions": [
    {"source_number": "<n>", "unique_contribution": "<what only this source adds>"}
  ],
  "new_understanding": "<what the combination makes clearer>",
  "relationship_counter_test": "<the strongest reason the grouping might fail>",
  "material_to_exclude": ["<material that belongs to the sources but not this cluster>"],
  "selection_decision": "<keep|split|demote|cut>",
  "selection_reason": "<why this decision fits the corpus>",
  "reader_value_reason": "<why it serves this digest's configured reader>",
  "value_basis": "<the consideration the selection actually rests on>"
}
```

Use one relationship value from the supplied vocabulary. Do not compose labels such as
`extension_plus_qualification`; that names two relationships and makes neither testable.
Every source number must have one specific contribution. If two contributions can be
swapped without loss, the sources are not contributing distinctly.

Record rejected or demoted groupings in `alternatives_considered`, with the decision and
reason. Frame must be able to see what was considered rather than only the winning result.

## Selection follows this digest's preferences

Apply the active digest's `Selection` instructions as written. Do not substitute a general
notion of quality, infer priorities from the digest's topic, or import emphases from another
digest or previous run.

For every promising candidate, record a concise `reader_value_reason` grounded in those
instructions and a `value_basis` that names what the decision actually rests on. Do not
assume that any particular basis is universally favored or disfavored by Synthesis MAX.

Recurring interests are affinity signals rather than a coverage quota. Material outside
them may still qualify when it serves the configured reader exceptionally well.

## Boundaries

* Decide what the corpus supports; do not design the finished edition's order or depth.
* Do not select a grouping merely because it would make a substantial-looking thread.
* Do not invent a relationship, fact, qualification, or reader preference.
* Keep an independently valuable source independent when synthesis would weaken its value.
