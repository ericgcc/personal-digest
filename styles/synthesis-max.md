# Synthesis MAX
One selective briefing: no separate article summaries. Merge the strongest material into an editorial synthesis organized around the relationships, patterns, tensions and ideas genuinely supported by the source set, with links back to every source.

## Style interface
| Dimension | Declaration |
| --- | --- |
| **Purpose** | Turn the strongest source material into one integrated briefing whose main value comes from meaningful relationships, patterns, tensions, and combined implications. |
| **Composition unit** | A synthesized editorial insight or thematic thread. |
| **Source relationship** | Cross-source synthesis is fundamental when supported; unrelated material must not be forced together, and a valuable source may stand largely alone when necessary. |
| **Selection model** | Highly selective: include material that contributes enough information, explanatory power, practical significance, novelty, or relationship value to justify space. |
| **Depth model** | Variable-high depth across a dense five-to-eight-minute body, normally 700–1,200 words excluding the catalog. |
| **Organization model** | Big Picture opening → two to five numbered synthesized threads determined by the evidence. |
| **Progression model** | Each thread develops a clear analytical arc from evidence or tension → relationship between sources → supported implication, with contributing material ordered by the argument rather than by source. |
| **Opening behavior** | Required `THE BIG PICTURE` opening that earns its place as the briefing's first editorial synthesis. |
| **Body behavior** | Numbered thematic threads with a deck, synthesis prose, claim-level citations, and source notes. |
| **Citation / provenance** | Permanent global numerical citations attached to supported claims/inferences plus thread-level source notes. |
| **Source catalog** | Required complete catalog of the substantively reviewed corpus, with stable numbering, canonical statuses, per-source reading time, and grouping controlled by `source_catalog_grouping` (`source-identity` by default; `editorial-topic` when explicitly configured). |
| **Ending behavior** | Stop immediately after the final source catalog. |
| **Writing character** | Analytical, connective, authoritative but restrained, precise, and intellectually alive. |
| **Optional extension points** | Zero or one digest-authorized callout inside a thread when the rendering profile supports it. |

## Writing reference profile
Apply the shared writing references with the following emphasis:

* `system/writing-reasoning-and-source-fidelity.md`—**full depth**. Evidence-led analysis and cross-source relationship testing are central to this style.
* `system/writing-editorial-prose.md`—**full depth**. The result should read like a strong analytical magazine essay, not a research paper or literature review.
* `system/writing-naturalness.md`—**full diagnostic pass** across the whole briefing.
* `system/writing-style-application.md`—preserve the Synthesis MAX boundary: the relationship is the composition anchor, and combined sources must add explanatory value unavailable from the sources separately.

Do not import academic surface conventions simply because the reasoning is analytical. Avoid ritual literature-survey language, repeated author-by-author attribution, and formal hedging formulas when claim-level citations and proportionate wording already make provenance clear.

## Synthesis mode
Produce one integrated briefing, not a collection of article summaries.

Before writing:

1. Form the catalog-eligible substantively reviewed corpus under the shared workflow, then assign every source in it a permanent sequential number based on input order.
2. Interrogate each promising source before synthesizing it: identify its actual thesis, strongest evidence/mechanism, meaningful caveats or anomalies, and what it uniquely contributes.
3. Evaluate each source for information value, explanatory power, practical significance, novelty and relevance to the broader source set.
4. Identify and classify meaningful relationships precisely: reinforcement, extension, qualification, contradiction, complementarity, shared cause/consequence, or independence.
5. For every proposed multi-source thread, ask what becomes more understandable only in combination, what each source uniquely contributes, and whether an anomaly, caveat, or plausible alternative grouping weakens the synthesis.
6. Select the material that provides enough value to justify space in a short briefing.
7. Choose the editorial structure that best reflects the evidence. Treat the initial synthesis as a working explanation, not a conclusion that later evidence must be made to fit.

Organize the briefing around synthesized ideas—not publications, authors or individual articles.

Seek synthesis where it is genuinely supported. Do not assume the source set has one unifying theme.

A strong section may answer questions such as:

* What broader pattern becomes visible when these sources are considered together?
* Where do sources reinforce, qualify or contradict one another?
* What principle or implication emerges from their combined evidence?
* Why does this matter beyond the individual source?

Explicitly explain connections rather than placing adjacent article summaries under a shared heading.

Prefer cross-source synthesis when meaningful, but do not force unrelated material together. A valuable source may stand largely on its own when it contains an important case study, explanation, technique or discovery with no honest counterpart in the source set.

Recurring coverage is not automatically important. Repetition may represent duplication rather than signal.

## Writing character
Write with analytical authority and restraint. The prose should make relationships visible without sounding as though every relationship is a revelation.

Start from the strongest concrete evidence, tension, or mechanism and let the synthesis emerge from it. Explain why sources belong together instead of relying on phrases such as "the broader pattern" or "the deeper lesson" to announce synthesis.

A good thread should feel discovered rather than imposed: the reader can see how the contributing evidence leads to the editorial inference. The thesis should emerge from source interrogation rather than precede it. Frame the thread before drafting so its evidence, relationship, and implication form one readable progression rather than a sequence of source observations. Distinguish sharply between what sources establish and what the briefing infers from them, and preserve a meaningful anomaly or qualification when it changes the explanation rather than smoothing it away.

Vary the rhetorical shape of threads. Some may begin with a contradiction, others with a concrete fact, mechanism, consequence, or question. Avoid repeating a polished `thesis → evidence → grand implication` cadence across the briefing.

Use memorable phrasing when it clarifies the relationship, but prefer precision to cleverness and proportion to profundity. Let analytical authority come from specific evidence and exact relationship verbs rather than academic register, repeated `not just X, but Y` framing, rhetorical Q&A, or generic claims that something signals a broader shift.

Do not use enumerative compression as a substitute for explanation. A run of nouns, features, techniques, stages, or examples is useful only when the sequence or comparison itself advances the argument. Otherwise, select the elements that matter and explain the mechanism, distinction, or relationship that makes them consequential. If several elements are essential, develop their roles instead of packing them into a dense list that merely signals breadth.

## Length and density
Aim for a dense five-to-eight-minute briefing.

Target roughly 700–1,200 words for the briefing body, excluding the final source catalog.

Use two to five thematic sections depending on the structure genuinely supported by the material. This is a permitted range, not a coverage target. Prefer a smaller number of developed insights over many shallow observations; when the evidence can support either shape, three well-developed threads are preferable to five compressed ones.

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
Open the briefing with one compact editorial synthesis of approximately 80–130 words with inline numerical citations. It must earn its place rather than act as a table of contents.

If one well-supported overarching pattern, tension, or question **emerges from the analyzed evidence**, articulate it directly. It may be modest. If the strongest material instead forms several distinct threads, frame two or three of the most compelling ones and any honest relationship between them without forcing a single thesis or upgrading topical proximity into significance.

Do not write inventory prose such as "today's edition moves from X to Y and closes with Z." Do not describe ingestion, filtering, ranking, or summarization. Put the most interesting analytical value early enough that the reader wants to continue into the threads.

### Thematic sections
Use numbered thematic sections. Their renderer-visible numbering and fixed component label are controlled by the matching rendering profile; they are not editorial copy and must not be renamed or adapted by the style.

Each section should normally contain:

* A one-sentence subtitle stating its central insight.
* As many paragraphs as the idea's analytical development genuinely requires. Allocate depth independently: a richer relationship may need several paragraphs, while a narrower one may need fewer. Do not infer paragraph count or section length from neighboring threads or from the HTML template.
* Inline numerical citations attached to the exact claims or synthesized inferences they support.
* A short thread-level source-notes component exposing the principal source names and their stable numbers, linked when a valid locator exists. Its visible label and treatment come exclusively from the matching rendering profile.

Section titles must describe the synthesized idea, pattern, question or tension—not repeat an article title.

Do not add an article-by-article roundup.

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
* Cross-source connections are substantive rather than superficial.
* Each multi-source thread passes the relationship, unique-contribution, evidence/inference, and counter-test checks in `system/writing-reasoning-and-source-fidelity.md`.
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
* The body remains dense enough for approximately five to eight minutes of reading.
* No section has been added merely to satisfy a target count or reading time.
* No closing section appears after `Sources`.
* `THE BIG PICTURE` earns its place with genuine analytical value and is not a prose inventory of the sections.
* Threads do not reuse the same rhetorical architecture or repeatedly announce "patterns" and "lessons" instead of demonstrating them.
* Enumerations do not replace explanation; when several elements are retained, their sequence, contrast, mechanism, or individual role is made clear.
* Concrete evidence, mechanisms, tensions, or consequences support the synthesis before abstraction outruns the sources.
* Memorable phrasing clarifies rather than manufacturing cleverness or profundity.
* The briefing reads as analytical editorial nonfiction, not as a literature review, research abstract, or author-by-author survey.
* Naturalness comes from evidence, judgment, rhythm, and proportion; repeated AI-shaped rhetorical patterns have been audited across the whole briefing.
