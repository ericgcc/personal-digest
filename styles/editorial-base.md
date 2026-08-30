# Editorial Base
This is the shared editorial quality floor inherited by every canonical digest style. It governs **how well the writing must work**, not the composition, source relationship, structure, or voice of any particular style.

A selected style may add a distinct writing character, and digest custom instructions may refine that character further, but neither may weaken this base quality standard. The production method that turns source material into finished prose lives in `system/editorial-process.md`. Shared craft references live in `system/writing-reasoning-and-source-fidelity.md`, `system/writing-editorial-prose.md`, `system/writing-naturalness.md`, and `system/writing-style-application.md`; they supply techniques, while the selected style determines how those techniques may be used.

## Supreme principles
**If the reader gives you their time, make every word earn it.**

**Every paragraph must give the reader a reason to read the next one.**

**Understanding comes before compression.**

The digest must not merely be correct, useful, and short. It should be a pleasure to read: clear enough to move quickly, coherent enough to follow without reconstructing missing steps, substantial enough to reward attention, and alive enough that the reader wants to continue.

## Quality floor
All digest prose must protect these qualities:

* **Clarity**—make the meaning easy to grasp without flattening important nuance.
* **Coherence**—develop an intelligible line of thought. Sentences, examples, and paragraphs must have a reason to follow one another rather than merely sharing a topic.
* **Specificity**—use concrete mechanisms, examples, evidence, numbers, distinctions, and consequences when they help the reader understand the central idea. Prefer showing why something matters through specifics before declaring its importance.
* **Orientation**—supply the context a knowledgeable reader needs before depending on unfamiliar terminology, assumptions, or technical detail.
* **Rhythm**—vary sentence length and paragraph movement so the prose does not feel mechanically generated.
* **Naturalness**—write like an excellent human editor, not like documentation, an executive-summary generator, or a templated LLM response. Naturalness must come from specific, explainable editorial choices—not fabricated personality, arbitrary irregularity, or detector-oriented tricks.
* **Intellectual honesty**—preserve uncertainty, limitations, disagreement, and scale; never manufacture importance or certainty.
* **Economy**—remove material that does not advance understanding, not merely words around material that should have been omitted.
* **Reader interest**—reveal meaningful value early and keep the thought progressing rather than circling or inventorying related facts.

Clarity comes first, but clarity alone is not enough. A paragraph can be individually clear and still fail if the reader cannot see how its sentences belong together.

## Coherence and narrative progression
Good nonfiction gives the reader a path through the material. This does not require anecdotes, drama, or a conventional story arc; even a technical explanation needs **narrative movement**.

For every substantive section:

* Establish one governing focus before adding support.
* Let each paragraph perform a distinct job in developing that focus.
* Order facts, examples, mechanisms, and recommendations according to the reader's path to understanding, not the order in which they were extracted from the source.
* Use a detail only when it advances the developing idea, supplies necessary context, tests it, qualifies it, or makes it concrete.
* Do not stack related facts or recommendations merely because they came from the same article.
* When the subject, abstraction level, or line of reasoning changes, orient the reader before continuing.

A useful internal test is whether the section's progression can be described simply as `A → B → C`. If no clear progression exists, restructure the section rather than polishing isolated sentences.

## Select before compressing
Brevity should come primarily from **selection**, not from squeezing every useful point into fewer words.

* Decide what the section is actually about and omit branches that do not serve that focus.
* A correct, interesting detail may still be the wrong detail for this piece.
* Prefer two well-chosen examples that make one idea clear over six compressed examples that blur together.
* Do not preserve every mechanism, recommendation, caveat, or fact just because it is present in the source.
* Leave valuable secondary depth in the original source when including it would damage coherence; if the selected style supports an optional depth cue, use that cue without importing style-specific components into other styles.

A shorter piece that teaches one thing well is better than a denser piece that mentions five things the reader cannot reconstruct afterward.

## Put value early without disorienting the reader
Readers scan before they commit. Make the beginning of every section, paragraph, and source entry justify the attention that follows.

Value early does **not** mean jumping immediately to the densest technical detail. Use the smallest amount of setup needed to make the value intelligible.

A strong sequence is often:

`orient → interest → explain`

or, when context is already obvious:

`specific observation → implication → explanation`

Use informative headings, focused paragraphs, and concrete entrances. Do not bury the strongest mechanism or consequence under generic setup, but do not force the reader to infer missing premises merely to achieve compression.

## Technical clarity
Technical precision must improve understanding rather than perform expertise.

* Introduce an unfamiliar term before relying on it when the surrounding context does not make it obvious.
* Render literal code, operators, paths, commands, identifiers, and syntax as code where the output format supports it.
* Prefer the literal technical meaning over vague metaphor. For example, say "compare the raw path string" rather than "check the spelling" when discussing path normalization.
* When a tiny concrete example explains a mechanism better than another abstract sentence, use the example.
* Omit implementation detail that is correct but distracts from the section's central line of thought.

## Wit, illumination, and agitation
When the material genuinely supports it, look for opportunities to provide:

* **Wit**—apt, economical phrasing that makes an idea easier to remember without obscuring it.
* **Illumination**—reveal a mechanism, distinction, pattern, implication, or connection so the reader sees the subject differently.
* **Agitation**—create productive intellectual friction by surfacing a real tension, counterintuitive result, trade-off, or challenged assumption.

These are possibilities, not quotas. Never manufacture cleverness, controversy, profundity, or surprise merely to sound editorial.

## Deliver insights; do not announce them
State the interesting thing directly instead of repeatedly announcing that an insight is coming.

Habitual scaffolding such as the following is a warning sign when the sentence can simply deliver the idea:

* "The key takeaway is…"
* "The deeper lesson is…"
* "The broader pattern is…"
* "The reusable insight is…"
* "What really matters is…"
* "The interesting thing is…"

Likewise, avoid content-description phrases such as "this article discusses" or "the author explores" when the underlying idea can be stated directly. Prefer ordinary exact verbs—including `is`, `has`, `uses`, `causes`, `changes`, or `depends on`—when they state the relationship more clearly than inflated alternatives such as "serves as," "represents," or vague language about being "associated with" something.

## Rhetorical variety
Do not give every selection the same linguistic architecture.

A section may open with a concrete fact, contradiction, consequence, question, mechanism, observation, short scene, or direct claim when the source supports that choice. Do not mechanically repeat `claim → explanation → broader lesson → takeaway` across the digest.

Rhetorical variety must never substitute for coherence. Choose the form that best carries the material's actual line of thought.

Judge repeated rhetorical devices by **pattern density**, not by isolated occurrence. Contrastive framing, rhetorical questions, triplets, em dashes, fragments, and explicit transitions are all legitimate tools; they become problems when they recur as default machinery rather than because the material earns them.

## Titles and headings
A title earns attention by making the underlying idea clearer, sharper, or more intriguing—not by trying to sound clever.

* Prefer specific meaning over slogan-like abstraction.
* Do not merely reuse the source headline when the selected style calls for editorial titles.
* Do not inflate a narrow technique into a universal principle.
* A memorable title is welcome when it remains faithful and immediately understandable.

## Openings must earn their existence
When a selected style includes an editorial opening, the opening must add value rather than function as a table of contents written in prose.

Use one of two approaches:

1. **If a genuinely interesting observation, tension, or relationship emerges from the selected material, say it directly.**
2. **If no such observation exists, create curiosity around two or three of the strongest pieces without pretending they form one thesis.**

Do not force a connection simply because an opening exists. Avoid inventory prose such as "today's edition moves from X to Y and closes with Z." Do not describe the ingestion, filtering, ranking, or summarization process.

## Intellectual restraint
Editorial confidence is not the same as grandiosity.

* Do not turn every article into a general law.
* Do not stretch a local result into a sweeping industry conclusion.
* Do not mistake recurring coverage for importance.
* Do not manufacture synthesis, conflict, or novelty because it makes the prose sound more sophisticated.
* Let a useful technique remain a useful technique when that is what the evidence supports.

A restrained sentence that is true and interesting is better than a profound-sounding sentence that outruns the source.

## Naturalness is an outcome, not a disguise
Do not optimize prose to evade AI detectors or to imitate accidental human messiness. Detector scores and isolated stylistic tells are unreliable; the deeper editorial failures matter more.

Use `system/writing-naturalness.md` as a diagnostic pass. In particular:

* Restore source-grounded specificity when generic significance language has smoothed it away.
* State concrete relationships instead of attaching superficial "highlighting/underscoring" analysis.
* Remove vague authority, false consensus, ritual hedging, and unsupported broader implications.
* Let section and paragraph shape vary because the material varies, not because randomness looks human.
* Never invent anecdotes, sensory detail, personal experience, quotations, mistakes, emotions, or biographical "fingerprints."

The strongest sign of editorial authorship is **explainable judgment**: why an idea was selected, why two sources were combined or kept apart, why a detail was included, what was omitted, and where the prose moves from source-supported fact to editorial inference.

## Voice boundary
This file defines quality, not one universal voice.

The selected style must declare its own **Writing character**. Digest custom instructions may further tune tone and vocabulary inside that character. The resulting prose may therefore feel brisk, patient, analytical, lively, or otherwise distinct while still meeting the same editorial quality floor.

Do not make every style sound alike in the name of consistency.

## Final quality standard
The staged editing sequence is defined in `system/editorial-process.md`. Before rendering, the finished prose must at minimum satisfy these outcomes:

* The reader can identify what each substantive section is actually about.
* The reason each paragraph follows the previous one is intelligible.
* Necessary context appears before dependent technical detail.
* Supporting material advances the central focus rather than accumulating beside it.
* The piece contains enough explanation to understand the selected idea without opening the source.
* Compression has not removed the logic that makes facts meaningful.
* The prose sounds natural in the selected style and remains faithful to the sources.
* Specific facts and mechanisms carry significance instead of generic importance language.
* Repeated rhetorical or structural patterns have been checked across the whole digest, not only within individual sections.
* The editor could explain the important selection, omission, source-relationship, and inference choices behind the finished piece.

If the prose is correct but incoherent, dense without being understandable, or dull because it reads like extracted notes, it is not finished.
