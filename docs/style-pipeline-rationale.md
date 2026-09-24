# Style Pipeline Rationale

**Audience:** maintainers. **Not** delivered to any model.

The operational stage documents in `system/style-pipelines/<style>/` are part of a stage's runtime
prompt. Everything in them is paid for on every run and read by a model that is trying to do the
stage's work, so they state executable responsibilities, required fields, decision rules and
prohibited behaviours — and nothing else.

The reasoning behind those rules is recorded here instead. It is the same reasoning, addressed to
a reader who is deciding whether the rules are right, rather than to a model that has to follow
them. When a rule in a stage document looks arbitrary or over-specific, its justification is
below.

See `docs/style-isolation-baseline.md` for the defect register these rules were written against,
and `system/editorial-pipeline-v2.md` §3.1–3.2 for the architecture.

---

## Why the stage documents exist at all

A style is defined by `styles/<style>.md`, which is authoritative for its identity and output
requirements. But a style file is one document serving several audiences at once: a reader of the
product, an editor reviewing an output, and a stage that has to act on a fraction of it.

Three things follow, and each is a reason for the stage documents:

1. **Not every stage should receive every rule.** The rules that govern how a document ends are
   irrelevant to a stage that plans one, and the rules that govern how a synthesis is formed are
   irrelevant to a stage that checks a catalogue. Routing is the style profile's job; the stage
   document is where the *operational consequence* of a subset of rules is stated.
2. **A style file states a contract; a stage needs a procedure.** "Each thread must explain a
   concrete subject" is a requirement. What it takes to satisfy it at a particular stage — which
   fields to fill, what makes a value unacceptable, what to do when the material does not fit —
   is not in the style file and should not be, because it is specific to one stage's work.
3. **The requirements have been broken before, in ways that were invisible.** The defect register
   is the evidence. Each rule below exists because something went wrong without it.

---

## Analyze

**Rule: assess the sources before assessing the relationships.**

A grouping can only be justified by what its members establish. If relationship-finding comes
first, the source assessments get written to support the grouping rather than to describe the
sources, and the grouping's weaknesses become invisible at exactly the point where they could have
stopped it.

**Rule: the cluster record is structured, and `relationship_type` is a closed vocabulary.**

Until Phase 2 the analysis wrote free-text relationship labels — `extension_plus_qualification`
was one, used in the September 21 run. A composite label names two relationships, and a thread
labelled that way cannot be tested against either. The same run used eight distinct `decision`
values including the hedges `selected_brief_or_catalog` and `catalog_only_or_brief`, which commit
to nothing and so cannot be compared with a frame's disposition vocabulary.

**Rule: `new_understanding` must say what becomes clearer through the combination.**

"Both sources discuss X" is not an answer, and a cluster that cannot give a better one has
independent value rather than combined value. This is the check that distinguishes synthesis from
a shared heading.

**Rule: `relationship_counter_test` must give the strongest reason the grouping might not be
justified.**

A counter-test that nothing could disprove is not a counter-test. The purpose is to catch the
decorative member: if removing one source would leave the thread intact, that source was not
contributing.

**Rule: `reader_value_reason` and `value_basis` are recorded per candidate.**

The digest's own configuration states what it downranks — typically technical novelty, scale and
detail volume standing alone. Recording the basis makes that judgement reviewable afterwards: a
selection that rests primarily on technical novelty is visible as such rather than hidden inside a
fluent justification.

**Rule: the priority order lives in the digest configuration, not here.**

`digests/<id>.md` owns "teach me something > give me something I can apply > …". Another digest
using this style may rank its values differently, so hard-coding one digest's order into the
pipeline would silently impose it elsewhere.

**Rule: record what was weighed and rejected.**

A candidate that was considered and demoted is an auditable decision. A candidate that never
appears is indistinguishable from an oversight.

### Why the Analyze stage receives the style at all

The most consequential defect in the baseline was that Analyze received no style document. Its
composition unit is *a concrete subject that at least two sources make easier to understand
together*, and nothing in its context said so. Selection was therefore made against a general
notion of article quality while the style's actual requirement was unavailable at the moment the
combination was decided — and unavailable later too, because Frame plans without the corpus and
Draft receives only what Frame declared. Analyze is the only stage that reads the whole corpus, so
it is the only stage that can judge a grouping against evidence.

The September 21 run shows the consequence. Analyze proposed a ten-source cluster for "agent
security and containment"; Frame ratified eight of them; the thread received 260 words and
published as an inventory of incidents at 32.5 words per source. No stage between selection and
publication was positioned to notice, because no stage had been asked what the group was *for*.

---

## Frame

**Rule: decide the edition's shape before designing its threads.**

`mode` is the edition's most consequential single field, and declaring it first means "no thread
qualified" is an available answer rather than a conclusion reached after failing to find one.

**Rule: cut the material before designing the threads, and resolve an oversized cluster in a fixed
order — reduce, split, then demote.**

The order matters. Reducing the source count is the cheapest fix and the most often correct.
Splitting is only a fix when each result is independently coherent; a split that produces two
fragments sharing one explanation has moved the problem. Demoting is a real editorial outcome, not
a failure: a source can be worth reading without being worth a thread.

Each rule here exists to close a specific escape. Solving an oversized thread by discarding
citations silently hides the loss. Solving it by compressing everything into a dense paragraph is
enumerative compression, which the style names as a defect. Solving a budget problem by adding
threads spreads the same material further without making it fit.

**Rule: the arithmetic must be exact and internally consistent.**

This is the rule with the clearest evidence. The September 21 frame planned 1,170 words against a
1,200 maximum — inside its ceiling, with no editing headroom — and the run published 1,654. The
September 22 frame planned 1,235 + 60 = 1,295 against the same maximum and published 2,113. Both
plans were arithmetically legitimate and both overstated what their allocations could explain. The
requirement to stay inside the budget was stated in prose in both cases. Nothing measured it.

Hence: exact numbers, because a range cannot be added up; `unit_depth_targets` consistent with the
per-unit fields, because a frame that states two different totals does not say how long the digest
is; and a reserve, because the writing stages add explanation as they work and a plan already at
its ceiling has nowhere to put it.

**Rule: `narrative_spine` is a sequence of explanatory moves, and `explanation_shape` names which
kind.**

The style forbids a single rhetorical template and permits a spine to develop a mechanism, a
contradiction, a comparison, a causal chain, a consequence or a tension. Naming the shape per
thread is what makes that requirement checkable; it is not a label that appears in the digest.

**Rule: every selected source needs a role, and the roles must be distinct.**

Two sources whose roles can be exchanged without changing the thread are not contributing
distinctly. The check is deliberately about distinctness rather than about quality: whether a role
is *good* is an editorial judgement, but whether two roles are *the same* is not.

**Rule: only retained units are held to the narrative contract.**

A `demote` or `cut` unit is not written, so requiring it to have two contributing sources and an
explainable allocation would reject a plan for correctly setting something aside. Set-aside units
are still checked for what they claim — a real disposition and real source numbers — because a
plan whose own account of itself cannot be read is a different problem from a plan that fails a
narrative requirement.

### Why the frame's own failure is treated specially

Frame is a gate. An invalid plan must not reach the writer, which is instructed to follow the plan
it is given, and the review stages diagnose prose rather than plans — so a rejected plan that
reached Draft would be published.

For `synthesis-max-v1` that means stopping. A derived recovery frame cannot satisfy the narrative
contract: it has no reader promise, no progression and no allocation, because inventing those is a
planning decision the recovery path is not entitled to make. Handing the writer a plan the
validator already refused is worse than not producing a digest.

For the legacy profiles the derived recovery frame is retained, because that is the behaviour the
pipeline specified before style profiles existed and a rollback must keep it. It is bounded — it
reads the analysis's candidate groupings rather than every `source_number` occurrence, which is
what previously expanded a "shortlist" to the entire corpus — and it is validated before
registration, so a recovery path cannot itself introduce an invalid artifact.

---

## Draft

**Rule: write from the approved plan and the projected evidence.**

Draft is not the planner and not the editor. The frame has already decided what each unit is
about, what the reader should understand, and which sources it needs. The stage's job is to make
that plan readable, and the reason the rule is stated as a prohibition is that the alternative —
re-planning inside the draft — happens invisibly and produces a document no plan accounts for.

**Rule: each thread gets one progression, not one paragraph per source.**

A source does not receive a paragraph because it was selected. This is the direct counterpart of
the Analyze counter-test and the Frame role check: both of those try to prevent a decorative
member entering the plan, and this one prevents it becoming a paragraph anyway.

**Rule: the writer receives only the frame's declared selection.**

The projection is the union of the *retained* units' `selected_source_numbers` and nothing else.
The citation map and `catalog_only.selected` are catalogue provenance — they describe what the
catalogue must list — and treating them as narrative authorisation is what let a fixture with two
retained sources project five. An `evidence_refs` entry outside the selection is reported rather
than merged, because a role describing evidence the writer will not receive is a description of
something that is not there.

**Rule: what the writer may not do.**

The list of prohibitions is short and each item maps to an observed failure: changing the
selection or order (which makes the frame's arithmetic meaningless), introducing facts outside the
projected evidence (the fidelity floor), and letting a template or a neighbouring thread's length
decide this thread's shape (which is how five threads came to be planned for a three-thread
budget).

---

## Review and revision

The five stages between draft and publication each narrow their attention further, and each is
capable of undoing work an earlier stage did for a good reason. The document states the invariant
and the per-stage boundaries; the reasoning is here.

**The invariant.** *The explanation is the product. Do not trade it for apparent concision, and do
not trade it for apparent completeness.*

In this style two failure directions are both live and they pull against each other:

* **Losing the explanation.** Deleting an orientation sentence, a definition, a causal step or a
  qualification to reach a word count removes the thing the thread existed to deliver. The symptom
  is a reader who can see the sources but cannot say what they jointly establish. Observed in the
  September 22 run: the line edit removed the glosses that defined three named tactics, and the
  reader review caught the regression — `regression_status: regressed`, `material_regression:
  true` — and a targeted repair restored them.
* **Manufacturing completeness.** Adding explanations, examples or qualifications so that every
  review finding is visibly addressed turns a thread into an inventory of source findings. The
  symptom is a thread whose length grew while its subject became less clear.

**A review that cannot be satisfied within the frame's allocation is describing a frame defect.**
That is the correct finding, and it is a finding about the plan rather than about the prose. Naming
it as one is what stops the revision stages from adding material indefinitely in pursuit of a
promise the allocation cannot keep.

**Why the boundaries are stated per stage rather than as one rule.** Each stage has a different
legitimate power, and a single "don't over-edit" instruction does not distinguish them. The
developmental review diagnoses and does not rewrite; writer revision revises but may not invent a
different synthesis; the line edit improves prose but may not remove explanatory content to reach a
length; the reader review measures but cannot retrofit an interpretation; targeted repair fixes one
located problem in one pass.

**Why this document reaches the evaluators too.** The three contracts the Python adapter accepted
before — role, reader and style interface — establish *who is judging* and *what the artifact
claims to be*. None of them states what a reviewer of this style must look for and must not ask
for, so a style-specific diagnostic could not be delivered to the judge at all. The document is
supplied to both audiences deliberately: the stages that edit prose and the stages that judge it
are answering the same question about the same style, and two copies would eventually disagree
about what a frame defect is.

---

## The domain example that used to be in `analyze.md`

The Analyze stage document carried a worked cluster example about decision-layer models, naming
real source numbers from a historical corpus. It was illustrative and it was also a hazard: it
anchored the stage to one subject, and a run whose corpus contained similar material could recruit
it. The example was replaced with a field-by-field skeleton that shows the same shape without
naming a subject.

For reference, the material it described — the decision layer as a typed, non-generative primitive
for agent calls, with source 24 specifying the mechanism, source 30 giving the delegation criteria,
and source 40 extending it to structured-data extraction — is a genuine example of a justified
three-source cluster with `relationship_type: complementarity`. It is recorded here so it remains
available when writing the Phase 7 fixtures for the other styles, and so a reviewer can see what
the stage was previously being shown.
