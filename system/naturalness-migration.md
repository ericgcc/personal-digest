# Naturalness: migration record

`system/writing-naturalness.md` was the complete naturalness manual injected into every editorial stage. In v2 it is no longer inline. Its contents were inventoried into four destinations:

* **house invariant** — a rule that belongs to this Digest System, kept in `system/naturalness-contract.md`;
* **WOPS operation** — a reusable transformation, supplied by the `wops` library and retrieved per diagnosed problem;
* **WOPS anti-pattern** — a detectable failure with named repair operations, supplied by WOPS;
* **obsolete / redundant** — content that no longer needs to exist because another canonical file or the retrieval layer covers it.

Universal craft principles move toward WOPS. Digest-specific voice, provenance, and house rules stay here. Source-fidelity semantics and digest-specific style semantics are deliberately **not** moved into WOPS.

| Section of `writing-naturalness.md` | Destination | Detail |
| --- | --- | --- |
| Intro: not an AI-detector evasion manual; clusters and repeated habits are the signal | house invariant + WOPS | The stance is restated in `naturalness-contract.md`; the cluster-detection content is what WOPS anti-patterns implement. |
| The core failure: smoothing away the specific | house invariant + WOPS | "Specificity beats assertion" and "restore the fact, not the claim of importance" stay house rules. Repairs come from WOPS `manufactured-significance`, `unsupported_significance`, and the operations `answer-so-what`, `interpret-evidence`, `trim-off-theme-detail`. |
| Superficial analysis: participial tails, "this shows that", vague connectedness | WOPS | Operations `make-causal-chain-explicit`, `connect-reason-evidence-warrant`; problem type `unsupported_connection`. The house rule "name the relationship" is restated in the naturalness contract. |
| Formulaic rhetorical performance: not-just-X-but-Y, rhetorical Q&A, triplets, inspirational pivot, punch-line fragments, dash default | WOPS anti-patterns | `rhetorical-formula`, `compulsive-triads`, `formulaic-closers`; problem types `rhetorical_formula`, `compulsive_triad`. |
| Structural symmetry | WOPS anti-pattern | `structural-uniformity`; problem types `structural_uniformity`, `paragraph_sprawl`. |
| Metronomic language | WOPS operation | `vary-sentence-rhythm`; problem type `repetitive_sentence_structure`. |
| Vague authority and false consensus | house invariant + WOPS | "Never convert one source's opinion into consensus" is a provenance rule and stays here. Detection is WOPS `unattributed-authority`. |
| Hedging and disclaimer overload | WOPS anti-pattern + operations | `empty-hedging`; operations `proportion-main-point-and-caveat`, `qualify-claim-to-evidence`. |
| Quotation and fact integrity | house invariant | Source-fidelity semantics. Not moved: WOPS does not know this project's sources. |
| No fake humanization | house invariant | Not moved. Distinctly a house rule about this digest's voice. |
| Explainable editorial choices | house invariant, made concrete | Now enforced by artifacts rather than by a question list: FRAME records why a source was selected, the developmental review records frame obligations, and `wops.json` records why each operation was retrieved. |
| Final pattern-density audit | house invariant | The whole-digest audit instruction stays in `naturalness-contract.md`. Individual repairs are retrieved, not recited. |
| "Do not ban these devices" | house invariant | Restated: a detected pattern is a defect only when the diagnosis says it is. |
| Duplication with the editorial prose guide (rhythm, "flow", voice) | redundant | The shared prose guide remains the craft reference for drafting; naturalness no longer restates it. |
| Detector-evasion framing | obsolete | The manual already disclaimed it; v2 removes the framing entirely rather than re-explaining it per stage. |

`system/writing-naturalness.md` is retained as an archival reference for the migration. It is no longer inlined into any stage.
