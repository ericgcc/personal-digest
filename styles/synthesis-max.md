# Synthesis MAX
One selective cross-source explanatory briefing: no separate article summaries and no single-source threads. Integrate the strongest material around concrete topics, questions, mechanisms, developments, or tensions that at least two sources make easier to understand together, with links back to every source.

This file is authoritative for what Synthesis MAX *is* and must produce. Which stage receives which part of it is declared by the `synthesis-max` style profiles in `tools/pipeline/style-profiles.mjs`; the stage-specific operational instructions those profiles name live in `system/style-pipelines/synthesis-max/`. See `system/editorial-pipeline-v2.md` §3.1.


## Style interface
| Dimension | Declaration |
| --- | --- |
| **Purpose** | Help the reader understand the strongest material through meaningful relationships between sources. The synthesis must improve explanation, not merely produce a higher-level interpretation. |
| **Composition unit** | A reader-understandable concrete topic, question, mechanism, development, or tension explained through at least two substantively contributing sources. |
| **Source relationship** | Cross-source synthesis is mandatory in every narrative thread. Prefer two or three sources. Four are permitted only when each one has a distinct, explainable role in the same concrete subject. No thread may declare more than four contributing sources. Single-source threads are not permitted. |
| **Selection model** | Highly selective: include material that contributes enough information, explanatory power, practical significance, novelty, or relationship value to justify space. |
| **Depth model** | Variable-high depth across a dense three-to-five-minute body, normally 700–1,200 words excluding the catalog. |
| **Organization model** | Big Picture opening → one to four numbered synthesized threads determined by the evidence; use fewer when the corpus cannot support honest multi-source grouping, and when no thread qualifies at all publish the explicit catalog-only edition. |
| **Progression model** | Each thread develops from concrete orientation → integrated explanation and source contributions → supported synthesis or implication, with material ordered by the explanation rather than by source. |
| **Opening behavior** | Required `THE BIG PICTURE` opening whose first duty is clear orientation; add cross-source interpretation only when it makes the picture easier to understand. |
| **Body behavior** | Numbered thematic threads with a deck, synthesis prose, claim-level citations, and source notes. |
| **Citation / provenance** | Permanent global numerical citations attached to supported claims/inferences plus thread-level source notes. |
| **Source catalog** | Required complete catalog of the substantively reviewed corpus, with stable numbering, canonical statuses, per-source reading time, and grouping controlled by `source_catalog_grouping` (`source-identity` by default; `editorial-topic` when explicitly configured). |
| **Ending behavior** | Stop immediately after the final source catalog. In the catalog-only edition, stop immediately after the catalog and its orientation. |
| **Writing character** | Explanatory, domain-accessible, and analytical; connective, authoritative but restrained, precise, and intellectually alive. |
| **Optional extension points** | Zero or one digest-authorized callout inside a thread when the rendering profile supports it. |

## Writing reference profile
Apply the shared writing references with the following emphasis:

* `system/writing-reasoning-and-source-fidelity.md`—**full depth**. Evidence-led analysis and cross-source relationship testing are central to this style.
* `system/writing-editorial-prose.md`—**full depth**. The result should read like a lucid analytical magazine briefing, not a research paper, literature review, or compressed conceptual essay.
* `system/writing-naturalness.md`—**full diagnostic pass** across the whole briefing.
* `system/writing-style-application.md`—preserve the Synthesis MAX boundary: every thread must synthesize at least two sources, and the relationship must make a concrete subject easier to understand than the sources would separately.

Do not import academic surface conventions simply because the reasoning is analytical. Avoid ritual literature-survey language, repeated author-by-author attribution, and formal hedging formulas when claim-level citations and proportionate wording already make provenance clear.

## Synthesis mode
Produce one integrated briefing, not a collection of article summaries.

Before writing:

1. Form the catalog-eligible substantively reviewed corpus under the shared workflow, then assign every source in it a permanent sequential number based on input order.
2. Interrogate each promising source before synthesizing it: identify its actual thesis, strongest evidence/mechanism, meaningful caveats or anomalies, and what it uniquely contributes.
3. Evaluate each source for information value, explanatory power, practical significance, novelty and relevance to the broader source set.
4. Identify and classify meaningful relationships precisely: reinforcement, extension, qualification, contradiction, complementarity, shared cause/consequence, or independence.
5. For every proposed thread, ask: **What concrete topic, question, mechanism, development, or tension do at least two sources help the reader understand better together—and what does each source add?** Then apply the relationship, contribution, evidence, counter-test, comprehension, and semantic-distance checks in `system/writing-reasoning-and-source-fidelity.md`.
6. Select the material that provides enough value to justify space in a short briefing.
7. Choose the editorial structure that best reflects the evidence. Treat the initial synthesis as a working explanation, not a conclusion that later evidence must be made to fit.

Organize the briefing around concrete shared subjects that become more understandable through synthesis—not publications, authors, individual articles, or abstract principles invented to connect distant material.

Seek synthesis where it is genuinely supported. Do not assume the source set has one unifying theme.

A strong section may answer questions such as:

* What concrete development, mechanism, question, or tension do these sources jointly explain?
* Where do sources reinforce, qualify or contradict one another?
* What does each source contribute that the others do not?
* What supported implication becomes visible after the shared subject is clear?

Explicitly explain connections rather than placing adjacent article summaries under a shared heading.

Every narrative thread must integrate at least two sources that contribute materially. Prefer two or three when they are sufficient. Four or more are welcome only when every source helps explain the same concrete subject and the thread remains easy to follow. A second source used only as decoration, analogy, or citation padding does not satisfy this requirement.

If a valuable source has no honest synthesis partner, keep it outside the Synthesis MAX narrative; it may still appear as `Worth reading` or `Reviewed` in the source catalog. Never create a single-source thread.

Do not group sources merely because they instantiate the same broad principle. If the relationship becomes visible only after translating distant domains into a slogan, metaphor, or high-level abstraction, keep them separate. The farther apart the source domains are, the stronger and more concrete the explanatory benefit must be.

Recurring coverage is not automatically important. Repetition may represent duplication rather than signal.

## Writing character
Write with analytical authority and restraint. The prose should make relationships visible without sounding as though every relationship is a revelation.

Write so the reader understands the material through the synthesis, not so the reader admires the synthesis itself.

Orient the reader in the concrete shared subject before compressing it into an inference. Explain what is happening, how it works, or what question is at stake; integrate what each source contributes; then let the synthesis or implication emerge. `Explain first, synthesize second` does not mean summarizing sources one by one. It means making the phenomenon intelligible before asking the reader to interpret a higher-level conclusion.

Start from the strongest concrete evidence, tension, or mechanism and let the synthesis emerge from it. Explain why sources belong together instead of relying on phrases such as "the broader pattern" or "the deeper lesson" to announce synthesis.

A good thread should feel discovered rather than imposed: the reader can see how the contributing evidence leads to the editorial inference. The thesis should emerge from source interrogation rather than precede it. Frame the thread before drafting so its evidence, relationship, and implication form one readable progression rather than a sequence of source observations. Distinguish sharply between what sources establish and what the briefing infers from them, and preserve a meaningful anomaly or qualification when it changes the explanation rather than smoothing it away.

Vary the rhetorical shape of threads. Some may begin with a contradiction, others with a concrete fact, mechanism, consequence, or question. Avoid repeating a polished `thesis → evidence → grand implication` cadence across the briefing.

Use memorable phrasing when it clarifies the relationship, but prefer precision to cleverness and proportion to profundity. Let analytical authority come from specific evidence and exact relationship verbs rather than academic register, repeated `not just X, but Y` framing, rhetorical Q&A, or generic claims that something signals a broader shift.

Do not use enumerative compression as a substitute for explanation. A run of nouns, features, techniques, stages, or examples is useful only when the sequence or comparison itself advances the argument. Otherwise, select the elements that matter and explain the mechanism, distinction, or relationship that makes them consequential. If several elements are essential, develop their roles instead of packing them into a dense list that merely signals breadth.

## Domain accessibility in synthesis
Synthesis MAX combines material that may carry different specialist vocabularies and assumed contexts. Write for an intelligent reader who is not necessarily familiar with any of those domains. The reader should gain access to the sources through the synthesis, not need prior access to understand it.

Begin each thread by establishing its concrete subject, relevant actors, situation, or mechanism in broadly understandable language. Introduce specialized terminology only after the reader has enough context to understand what it refers to and why it matters.

Preserve domain terms that carry necessary precision, but explain them at the point of use through their function, effect, referent, consequence, or a concise example. Do not require the reader to infer their meaning from adjacent jargon.

Move through one level of abstraction at a time:

`concrete subject → source evidence or mechanisms → relationship → implication`

Do not combine unfamiliar terminology, compressed source context, metaphor, and editorial inference in the same sentence. Unpack them in the order required for understanding.

Every additional domain creates an orientation cost. Include a cross-domain source only when its concrete explanatory contribution is strong enough to repay that cost within the thread's limited reading budget. Conceptual similarity alone does not repay it.

Let each paragraph perform one primary explanatory job. If several unfamiliar concepts are essential, establish their roles and relationships before asking them to support a broader conclusion. A reader should never need to understand the synthesis in order to reconstruct what the underlying material was about.

## Length and density
Aim for a dense three-to-five-minute briefing.

Target roughly 700–1,200 words for the briefing body, excluding the final source catalog.

Use one to four thematic sections depending on the structure genuinely supported by the material. This is a permitted range, not a coverage target. Prefer a smaller number of developed insights over many shallow observations; when the evidence can support either shape, three well-developed threads are preferable to four compressed ones.

Every thread's reading budget must be large enough to explain what it is about. A thread that names many sources without enough space to state what each contributes has stopped explaining and started cataloguing; reduce its sources, split it, or move its least essential material to the source catalog. A source needs at least roughly one explanatory sentence of space, and a thread needs room beyond that for the orientation and the relationship it exists to explain.

Let information density determine length. Never create, split or expand a section merely to satisfy a target count or reading time.

Every paragraph must contribute at least one of the following:

* New understanding.
* Practical or conceptual value.
* Cross-source synthesis.
* An important qualification, disagreement or tension.
* A clear reason to read an original source.

Remove repetition aggressively. Do not restate a section's thesis in its conclusion.

## Required structure
### The Big Picture
Open the briefing with one compact orientation of approximately 80–130 words with inline numerical citations. Its first duty is to tell the reader, in plain language, what the most important development, mechanism, question, or tension is and why it matters. Establish the concrete world of the briefing before introducing specialized vocabulary or an overarching interpretation. Add a cross-source interpretation only when it makes that picture clearer. It must earn its place rather than act as a table of contents.

If one well-supported overarching pattern, tension, or question **emerges from the analyzed evidence**, articulate it directly. It may be modest. If the strongest material instead forms several distinct threads, frame two or three of the most compelling ones and any honest relationship between them without forcing a single thesis or upgrading topical proximity into significance.

Do not write inventory prose such as "today's edition moves from X to Y and closes with Z." Do not describe ingestion, filtering, ranking, or summarization. Do not open with a polished abstraction whose concrete meaning becomes clear only after reading the body. Put the clearest high-value orientation early enough that the reader wants to continue into the threads.

### Thematic sections
Use numbered thematic sections. Their renderer-visible numbering and fixed component label are controlled by the matching rendering profile; they are not editorial copy and must not be renamed or adapted by the style.

Each section should normally contain:

* Material from at least two substantively contributing sources, and never more than four.
* A one-sentence subtitle that identifies the concrete subject and states what the combined material helps explain.
* As many paragraphs as the idea's analytical development genuinely requires. Allocate depth independently: a richer relationship may need several paragraphs, while a narrower one may need fewer. Do not infer paragraph count or section length from neighboring threads or from the HTML template.
* Inline numerical citations attached to the exact claims or synthesized inferences they support.
* A short thread-level source-notes component exposing the principal source names and their stable numbers, linked when a valid locator exists. Its visible label and treatment come exclusively from the matching rendering profile.

Section titles and subtitles must let the reader identify the concrete subject before reading the body. Use the most broadly understandable vocabulary that preserves the necessary precision; a specialized term may appear when essential, but it must not carry the full burden of orientation. Prefer specific mechanisms, developments, questions, or consequences over slogans, metaphors, or abstract conclusions that the body must decode. Do not repeat an article title.

Do not add an article-by-article roundup.

### The catalog-only edition
When no honest cross-source thread qualifies — every candidate would need a broad abstraction, a slogan, or a metaphor to hold it together — do not manufacture one. Publish the explicit catalog-only edition instead: the orientation, then the source catalog.

This is a legitimate outcome, not a failure, and it is rare. It is bounded by one condition: it is only honest when the corpus genuinely offers no concrete subject that two or more sources make easier to understand together. A corpus with an eligible thread must use it. The catalog-only edition is also longer than it looks, because the complete catalog of every substantively reviewed source remains required, and is exempt from the body-length expectation that governs a threaded briefing. Its orientation should tell the reader plainly what the edition is: the corpus was read, and nothing in it was worth combining.

Do not pad it. There are no threads, no thread source-notes, and nothing after the catalog.

## Citations
Use numerical citations instead of article names in the prose.

Assign each catalog-eligible substantively reviewed source one stable number and reuse it everywhere.

Render every inline citation using the permanent source number:

`[7]`

When a valid source locator exists, make the numerical citation clickable. When the source is email-only and no reliable locator exists, keep the same visible numerical citation as a non-clickable reference. Never fabricate a destination merely to preserve clickability.

When several sources directly support the same claim or jointly contribute to the same synthesized inference, group their citations:

`[3] [7] [12]`

Place citations immediately after the claim or inference they support.

When a synthesized claim is derived from several sources, cite the contributing sources together on that claim rather than only citing them separately in surrounding paragraphs.

A citation may either:

* Directly support a factual claim established by the source.
* Identify the sources from which a synthesized editorial inference is reasonably derived.

Use language that makes editorial inference clear when a conclusion goes beyond what any single source states directly.

Never cite a source that does not materially contribute to the preceding claim or inference.

Do not add citations merely to make an interpretation appear more widely supported.

Do not write full article titles or raw URLs inside the narrative; retain the numerical citation.

## Final source catalog
End with a section titled `Sources`.

List every catalog-eligible substantively reviewed article or newsletter item, including material not selected for the narrative. Do not list operational exclusions or non-editorial residue merely to document that they were encountered.

Preserve the permanent numbering used throughout the briefing.

Resolve grouping from digest frontmatter:

* `source-identity` (default)—use the most useful stable identity in this order: newsletter/publication, sender/editorial source, then recurring author identity. Use `Other sources` only when no meaningful identity exists. Within a group, do not repeat the group name on every row; show an author only when it adds information beyond the heading.
* `editorial-topic`—when explicitly configured, derive a small set of reader-oriented topic headings from the reviewed corpus and assign each source once under its primary navigational topic. Do not simply copy thread titles, because a source may support several synthesized threads; do not imply exclusive contribution. Show author/publication/sender on every row when available.

Keep each source's permanent global number unchanged inside its group; grouping must never renumber citations or alter the synthesis. Source identity remains the preferred default for auditability in this style.

For every source include:

* Its number.
* The article/item title as a clickable link when a valid source locator exists; otherwise the plain title with email-only provenance.
* The author or publication when available.
* The original source reading time as `N min` whenever the item was substantively read, using the shared source-reporting rule.

Add a short status label when it conveys editorial or operational state:

* `Selected`
* `Worth reading`—the source was not selected for the narrative, but after reading it the editor would still actively recommend the original if the reader has extra time. Use it sparingly—normally zero to three sources, occasionally more only in an exceptional corpus.
* `Reviewed`—the source was substantively reviewed but was neither selected nor marked `Worth reading`.
* `Limited content`

`Email-only` may appear as provenance beside one of these outcomes; it is not a competing selection status. Operational outcomes such as duplicate, promotional/administrative, social notification, low signal, inaccessible, or excluded before read remain internal and do not appear in the catalog.

`Selected` and `Worth reading` are mutually exclusive. `Worth reading` remains a catalog-only recommendation and does not create a narrative thread. Every source cited in the narrative is `Selected`; derive `Worth reading` only from the unselected remainder and validate that the sets are disjoint. When a status badge is shown for substantively read material, append the reading time with a middle dot, for example `Worth reading · 8 min` or `Reviewed · 4 min`.

Do not explain why each unselected source was omitted.

The catalog exists for transparency and navigation; it is not another summary section.

## Ending rules
Finish immediately after the source catalog.

Do not include:

* "What was left out."
* "Final signal."
* A concluding recap.
* A generic list of takeaways.
* A motivational closing.
* A restatement of The Big Picture.

## Quality control
Before returning the briefing, verify that:

* It reads as one editorial briefing rather than multiple summaries.
* Every narrative thread integrates at least two substantively contributing sources; no thread is single-source and no second source is merely ornamental.
* Cross-source connections are substantive rather than superficial.
* Each thread passes the relationship, unique-contribution, evidence/inference, counter-test, comprehension, and semantic-distance checks in `system/writing-reasoning-and-source-fidelity.md`.
* Each selected source's main explanatory value remains recoverable after reframing and integration.
* Combining the sources makes the underlying subject easier to understand rather than merely producing a more abstract idea that can contain them.
* Two or three sources are preferred when sufficient; threads with four or more still revolve around one concrete subject and remain easy to follow.
* An intelligent reader outside the contributing source domains can explain what each thread is about, what happened or how it works, and why it matters after one reading.
* Necessary specialized terms are understandable through their function, effect, referent, consequence, or a concise example before the prose depends on them.
* No sentence asks the reader to decode unfamiliar vocabulary, missing context, metaphor, and editorial inference simultaneously.
* Every cross-domain source provides enough concrete explanatory value to justify the additional orientation it requires.
* The working thesis emerged from the material and was revised when caveats or anomalies required it; the source set was not recruited to defend a preselected grand idea.
* Unrelated sources have not been forced into a common narrative.
* Editorial inference is distinguishable from source-supported claims.
* Multi-source synthesized claims cite the contributing sources together when appropriate.
* Every factual claim has the appropriate numerical citation.
* Every linked citation points to the correct original source; non-linkable email-only citations remain stable and are not given fabricated destinations.
* Citation numbers remain consistent from beginning to end.
* All catalog-eligible substantively reviewed sources appear in the final catalog, and no operational exclusion appears there.
* The final catalog uses the configured `source_catalog_grouping` mode without changing permanent source numbers; `source-identity` remains the default, while configured topic grouping shows provenance on every row and does not falsely mirror the synthesis threads.
* Every narrative source is `Selected`; `Worth reading` is drawn only from unselected sources, and the sets are disjoint.
* The strongest material receives the most space.
* Repetition across sources is compressed rather than mistaken for importance.
* The body remains dense enough for approximately three to five minutes of reading.
* No section has been added merely to satisfy a target count or reading time.
* No closing section appears after `Sources`.
* `THE BIG PICTURE` gives clear orientation before interpretation, earns its place with genuine analytical value, and is not a prose inventory of the sections.
* A reader can identify the concrete subject of every thread from its title and subtitle without first decoding a slogan or metaphor.
* Threads do not reuse the same rhetorical architecture or repeatedly announce "patterns" and "lessons" instead of demonstrating them.
* Enumerations do not replace explanation; when several elements are retained, their sequence, contrast, mechanism, or individual role is made clear.
* Concrete evidence, mechanisms, tensions, or consequences support the synthesis before abstraction outruns the sources.
* Memorable phrasing clarifies rather than manufacturing cleverness or profundity.
* The briefing reads as lucid analytical editorial nonfiction, not as a literature review, research abstract, author-by-author survey, or collection of compressed conclusions.
* Naturalness comes from evidence, judgment, rhythm, and proportion; repeated AI-shaped rhetorical patterns have been audited across the whole briefing.
