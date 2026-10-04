## Required structure
### The Big Picture
Open the briefing with one compact orientation within the resolved opening-word range and use inline numerical citations. Its first duty is to tell the reader, in plain language, what the most important development, mechanism, question, or tension is and why it matters. Establish the concrete world of the briefing before introducing specialized vocabulary or an overarching interpretation. Add a cross-source interpretation only when it makes that picture clearer. It must earn its place rather than act as a table of contents.

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

## Length and density
Aim for a dense three-to-five-minute briefing.

Keep the briefing body within the resolved body-word range, excluding the final source catalog.

Use a number of thematic sections within the resolved unit range and supported by the material. The range is a permission boundary, not a coverage target. Prefer a smaller number of developed insights over many shallow observations.

Every thread's reading budget must be large enough to explain what it is about. A thread that names many sources without enough space to state what each contributes has stopped explaining and started cataloguing; reduce its sources, split it, or move its least essential material to the source catalog. A source needs at least roughly one explanatory sentence of space, and a thread needs room beyond that for the orientation and the relationship it exists to explain.

Let information density determine length. Never create, split or expand a section merely to satisfy a target count or reading time.

Every paragraph must contribute at least one of the following:

* New understanding.
* Practical or conceptual value.
* Cross-source synthesis.
* An important qualification, disagreement or tension.
* A clear reason to read an original source.

Remove repetition aggressively. Do not restate a section's thesis in its conclusion.

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
