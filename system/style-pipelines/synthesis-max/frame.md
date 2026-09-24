# Synthesis MAX — Frame

**Stage:** `frame` · **Style:** `synthesis-max` · **Profile:** `synthesis-max-v1`

This document is operational. It states what *this stage* is responsible for in this style. `styles/synthesis-max.md` remains authoritative for the style's identity and output requirements, and `system/contracts/frame.md` remains authoritative for the stage's role.

---

## The two things this stage controls

Frame is the authority on what Draft may see and on how much room it has.

1. **The amount of material the writer receives.** A unit that declares more sources than its allocation can explain does not fail here. It fails at Draft, as an inventory of findings, and no later stage is positioned to fix it: Draft follows the plan it is given, and the review stages diagnose prose rather than plans.
2. **The edition's arithmetic.** Your per-unit allocations are what the writer spends. A plan that sums to more than the style permits is not a plan for the permitted document.

Both are checked deterministically before Draft sees anything, and a plan that violates them is sent back once, with the specific problems, for you to correct. That is a revision opportunity rather than a rejection: return a corrected plan that fixes exactly what the findings name.

---

## What you receive

| Document | What it contributes here |
| --- | --- |
| `system/contracts/frame.md` | The stage's role, the unit rule, the disposition vocabulary, and how to resolve material that does not fit. |
| `system/style-contract.md` | The interface vocabulary the style's `## Style interface` section uses. |
| `system/contracts/reader-contract.md` | What a reader must be able to follow, independent of style. |
| `styles/synthesis-max.md` § `## Style interface` | The style's composition unit, source relationship, depth model, organisation model, opening behaviour and catalogue requirement. |
| `styles/synthesis-max.md` § `## Synthesis mode` | How threads are formed, and the tests a proposed thread must pass. |
| `styles/synthesis-max.md` § `## Required structure` | The structure each thread and the edition must take, the source-notes component, and the catalog-only edition. |
| `styles/synthesis-max.md` § `## Length and density` | The body budget, the thread range, and the evidentiary floor. |
| `styles/synthesis-max.md` § `## Citations` | Which sources a thread may cite: only those that materially contribute to the claim they support. |
| `styles/synthesis-max.md` § `## Final source catalog` | The catalogue's grouping and status semantics, which this stage records. |
| `digests/<digest-id>.md` | This digest's reader interests and selection priorities. |
| `system/style-pipelines/synthesis-max/frame.md` | This document. |

You do **not** receive `## Ending rules`: you plan a document, you do not terminate one, and the ending rule is enforced by the stage that publishes it. You do not receive `## Writing character` or `## Domain accessibility in synthesis`: you work in directions and structured fields, not prose.

---

## Your responsibility in this style

### 1. Decide the edition's shape before designing its threads

Declare `mode` first — it is the edition's most consequential single field.

* **`"threads"`** — the normal edition. One to four retained threads.
* **`"catalog_only"`** — no thread qualified. The edition is the orientation plus the complete source catalogue.

`"catalog_only"` is honest when, and only when, every candidate grouping would need a broad abstraction, slogan, or metaphor to hold together. It is not a way to publish a short edition with threads still in it, and it is not a way to avoid the work of finding a relationship. If any concrete subject is genuinely made easier to understand by two or more sources, that thread exists and must be planned.

### 2. Cut the material before designing the threads

This is the stage's constructive act, and it comes before the planning rather than after it. Take the clusters Analyze proposed and reduce them to what can actually be explained.

The limits are stated in `styles/synthesis-max.md`, and the deterministic checks mirror them: **one to four threads**, **two to four contributing sources per thread**, and **enough words per source that its contribution can be stated** rather than named.

When a candidate cluster is too large, resolve it in this order:

1. **Reduce the source count** to the members that actually carry the subject. A source that adds only a further example of a point already made is not contributing; it is padding the citation count.
2. **Split** into two threads, but only if each resulting thread is independently coherent — each with its own concrete subject, passing the unit rule on its own. A split that produces two fragments sharing one explanation has not solved anything.
3. **Demote** the least essential material to the source catalogue. This is a real editorial outcome, not a failure: a source can be worth reading without being worth a thread.

Never solve an oversized thread by planning to discard its citations silently. Never solve it by compressing all of its material into a dense paragraph — enumerative compression is the symptom the style names explicitly. Never solve a budget problem by adding threads: a plan that does not fit is made to fit by cutting, not by spreading.

### 3. Give every retained thread the fields its explanation needs

Reuse the fields `system/contracts/frame.md` already defines rather than inventing parallel ones. In this style they carry:

* **`central_focus`, `reader_promise`, `plain_language_setup`, `reader_needs_to_understand`, `orientation_needed`** — what the thread is about and what the reader must already have. A thread whose `plain_language_setup` cannot be written without a specialised term is a thread whose subject is not yet concrete.
* **`narrative_spine`** — the ordered explanatory moves, not a dramatic arc. In this style a spine may develop a mechanism, a contradiction, a comparison, a causal chain, a consequence, or a tension. It must begin from orientation and end at the relationship or the implication, which needs at least two moves.
* **`explanation_shape`** — which of those kinds of explanation this thread uses, written as **exactly one** of these six words: `mechanism`, `contradiction`, `comparison`, `causal_chain`, `consequence`, `tension`. State the value alone. A phrase describing the moves, such as `"mechanism, closed by a measured comparison"`, is not a value from the vocabulary and cannot be counted or varied; the moves themselves belong in `narrative_spine`, which is where they are read. Declaring the shape is what stops the edition becoming one rhetorical template repeated: if every thread is a mechanism explanation, the digest reads as a format rather than as a set of discoveries. Vary it when the material genuinely differs; do not vary it by inventing a difference that is not there.
* **`selected_source_numbers`** — the authoritative evidence selection, and the whole of what the writer receives. Two to four numbers.
* **`evidence_refs`** — one entry per selected source, each with what is drawn from it and **the distinct role it plays**. Distinctness is the test: if two sources' roles can be exchanged without changing the thread, one of them is probably not needed. An identical role string on two sources is the signature of decoration.
* **`branches_to_cut`** — correct material belonging to these sources but not to this thread.
* **`depth_target_words`** — the thread's allocation, as an exact number.
* **`single_idea_check`** — one sentence confirming the thread carries one idea, or naming why it does not.

### 4. Make the arithmetic add up

The plan's numbers are read as a single budget, and the checks are exact:

* The Big Picture receives an exact number of words inside the style's stated band. Record it in `big_picture_words`.
* Each retained thread's `depth_target_words` is an exact number.
* `unit_depth_targets` maps every retained unit id to its allocation, and its values must equal the units' own `depth_target_words`.
* `total_unit_words` is the sum of those allocations.
* `total_body_words` is `big_picture_words` + `total_unit_words`.

The total must not exceed the style's maximum, and the ceiling that binds is lower than it looks. The style reserves headroom for the writing stages to add explanation as they work, and a plan already at the maximum has nowhere to put it.

The reserve is 15% of the maximum: of 1200 words, 180 are held back. So **`total_body_words` must not exceed 1020** — that is the maximum the plan is allowed to spend, not 1200. Leave the difference unplanned deliberately. When the total is over 1020, the remedy is in §2 above — reduce, split, or demote — and not a smaller number on an unchanged plan.

The minimum is not a target to fill either. The style's band is 700–1200 words; a plan that comes in well under 1020 is a plan with more room to explain each retained source, which is the trade this style makes.

Approximate or ranged allocations do not satisfy this. Write exact numbers; a range cannot be added up, and a plan whose arithmetic cannot be checked is a plan nobody can hold to.

### 5. Carry the analysis forward honestly

Preserve the analysis's selection outcomes across the selected, worth-reading and reviewed sets, and carry per-source reading minutes through unchanged. Record what you set aside and why, so the omission is deliberate and auditable rather than invisible.

Where Analyze recorded a `relationship_counter_test` for a cluster you retained, that caveat is part of the thread's obligation: either it is addressed in the plan or the thread is not as strong as it looked.

---

## Boundaries

* Do not write the digest. Directions, labels, working titles and structured fields only.
* Do not introduce a source, claim or relationship the analysis does not support.
* Do not state a reader promise the selected evidence cannot keep.
* Do not resolve a framing problem with more prose, and do not resolve it by compressing two ideas into one unit.
* Do not pass the plan to the writer knowing it exceeds the budget. An oversized plan is a decision to publish an oversized digest.
* Return only the JSON artifact. No commentary, no code fence, no tools.
