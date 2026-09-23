# Known issues

Open issues that span more than one component. Each entry records what is **confirmed by evidence**, what is only **hypothesised**, and what would settle the question. Entries are not fixed until moved to a resolution note at the bottom.

Last updated: 2026-09-15

---

## KI-001 — Article links missing for `inline-newsletter` sources

**Status:** open, unconfirmed
**Component:** orchestrator (corpus construction)
**Owner:** orchestrator, not the local runner
**Severity:** medium — affects reader navigation and catalog quality, not digest correctness

### Observation

In run `test-tech-bi-daily-20260915-bc0a15fd9af1`, 39 of 63 catalog-eligible sources have `canonical_url: null`. All 39 use the `inline-newsletter` adapter; all 24 with a URL use `link-newsletter`. So the split is exactly by adapter.

The user's assessment is that many of those email-only items **do** link to their original article, and that the link was lost during acquisition rather than being absent. The rendering side handled this correctly: 36 clickable citation pills for sources with a URL, 80 non-clickable `citation-plain` pills for sources without, which is what `system/html-rendering.md` requires.

### What the evidence supports

`full_text` is **extracted plain text**. If the orchestrator converted the email HTML to text without preserving anchor hrefs, then article links were present in the original email and are now unrecoverable from the corpus. This artifact cannot distinguish "there was never a link" from "the link was stripped".

Scanning `full_text` for URLs across the 39 email-only sources:

| Finding | Count |
| --- | --- |
| Contain at least one non-noise URL | **7** |
| Contain no URL at all | **32** |

The 7 hits are mostly **not** the article link — they are URLs mentioned *inside* the article body:

| Source | URL found | What it actually is |
| --- | --- | --- |
| #28 Data Engineering Weekly #287 | `luma.com/dataforai-h5ua`, `datastreaming-summit.org/dss2026` | event registrations |
| #58 What It Takes to Build a Production Agent Harness | `hermes-agent.nousresearch.com/install.sh`, `localhost:5173/api` | install script, local dev URL |
| #36 You're Probably Using Claude Code Wrong | `tesla.com/model3`, `github.com/teng-lin/notebooklm-py` | an example, a referenced tool |
| #9 "You know which gazelle gets eaten by the lion?" | `neal.fun/unusual-suspects/` | a site referenced in the piece |
| #38 Amodei slows frontier | `refer.tldr.tech/af7990fa/2` | tracking redirect |
| #41 Brownfield Agentic Engineering | `fandf.co/4d7aN6O` | shortlink |
| #55 Apple launches iOS 27 with AI Siri | `mcp.descope.com` | product site |

So the corpus contains **no recoverable article link** for 32 of 39 sources, and for the other 7 the URLs are incidental.

**Conclusion: the hypothesis is plausible but this artifact cannot confirm it.** The evidence needed — the original email HTML or its anchor `href` values — is not in the corpus.

### Contributing factor found: probable adapter misclassification

Several sources tagged `inline-newsletter` look like **link roundups**, which per `system/workflow.md` should be `link-newsletter` — and in that mode the workflow extracts their candidate links as separate sources.

| Source | URLs found in `full_text` | Title |
| --- | --- | --- |
| #28 | 11 | Data Engineering Weekly #287 |
| #33 | 1 (plus shortlinks) | Postgres at 118M QPS, ChatGPT Work Data Agent |
| #38 | 1 (tracking redirect) | Amodei slows frontier, ARC-AGI-4, Cursor Project |
| #53 | 2 | Why you should work on AI for AI Research |

`Data Engineering Weekly #287` is a link roundup by name and shape. Classifying it as inline means its article links are never extracted, and the digest loses every source inside it.

This is a **second, independent** mechanism by which links go missing, and it is diagnosable from the corpus alone.

### How to settle KI-001

Any one of these is decisive:

1. Locate one of the 39 emails in Gmail, confirm whether it contains an article link, and compare against the corpus record for that `originating_gmail_message_id`.
2. Check whether the orchestrator's HTML-to-text conversion preserves anchor hrefs. If it strips them, links are being lost at extraction.
3. Compare `source_emails[].title` and the email body against the source record's `title`. A newsletter whose own subject line is the article title usually links to that article.

### Why this is orchestrator-side, not runner-side

The local runner never constructs the corpus. `sources.json` is produced by the scheduled-task agent, and `programatic-layer-revamp.md` locks its schema (decision D5): changing it changes the orchestrator contract. The runner consumes `canonical_url` as given.

---

## KI-002 — `Email-only` provenance is dropped during rendering

**Status:** confirmed
**Component:** render stage (local runner)
**Severity:** medium — makes 39 catalog rows look unexplained

### Observation

| Artifact | `Email-only` occurrences |
| --- | --- |
| `final-polish/output/final.md` | **39** |
| `render/output/email.html` | **0** |

The approved prose marked every URL-less source `Email-only`. The delivered email carries none of those markers.

### Impact

A reader sees 39 catalog rows as bare titles with no link and **no indication why**. That reads as a broken catalog rather than intentional email-only provenance. It is very likely what prompted the original report of "no links to the original sources".

`system/workflow.md` permits the marker: *"in final source catalogs, list the title and provenance without a link and optionally mark it `Email-only`."* `final.md` did this correctly.

### Possible cause

`render` is the **only stage with thinking disabled**, and it is the only stage that lost information. Suggestive, not proven — the correct instruction was present in its context.

### Next step

Re-run the render stage with thinking enabled on the same `final.md` and compare. `resume --from-stage render` does this against the existing run without redoing editorial work, if the render output is first removed.

---

## KI-003 — Verifier cannot detect `final.md` to `email.html` fidelity loss

**Status:** confirmed
**Component:** `tools/verify-run.mjs`
**Severity:** medium — a whole class of defect is currently unobservable

### Observation

The verifier reported **0 errors** on the run above while KI-002 was present.

It checks citations against the **corpus**, but never compares the approved prose against the **delivered artifact**. Any content that exists in `final.md` and is dropped or altered during rendering is therefore invisible.

### Impact

Rendering is the last step before delivery and receives the least scrutiny. Silent loss there reaches the reader directly.

### Next step

Add a `final.md` to `email.html` fidelity check comparing, at minimum: citation counts and numbers, source catalog row count, and the presence of provenance markers such as `Email-only`. Fuzzy prose comparison is not appropriate, but structural counts are exact and cheap.

---

## KI-004 — Email-only sources get a search-scoped Gmail URL instead of a deep link

**Status:** confirmed
**Component:** orchestrator (corpus construction)
**Severity:** low — the runner correctly refuses to link it

### Observation

All 39 email-only sources carry a `resolved_source_locator` of the form:

```text
https://mail.google.com/mail/u/0/#search/label%3ANewsletters+newer_than%3A3d/<message-id>
```

That is a **search result**, and `system/workflow.md` forbids using a search result as a source locator. The runner correctly declined to link it, which is why those catalog rows are plain text.

### A proper link is constructible

The source records do carry the identifier needed:

| Field | Example | Populated |
| --- | --- | --- |
| `originating_gmail_message_id` | `1a09433932b4027e` | yes, all 39 |
| `stable_source_id` | `gmail:1a09433932b4027e` | yes, all 39 |
| `source_emails[].gmail_thread_id` | `1a09433932b4027e` | yes, all 55 |

A direct link of the form `https://mail.google.com/mail/u/0/#all/<id>` would be a legitimate deep link under the locator policy, where the search URL is not.

### Next step

Either have the orchestrator emit a direct Gmail message/thread deep link when no external URL exists, or explicitly accept that email-only sources remain unlinked. Do not relax the runner's refusal — linking a search result would violate the locator policy.

---

## Resolution notes

*(Move entries here when closed, with the commit and the evidence that closed them.)*

---

## KI-005 — A judge response containing a raw control character was discarded

**Status:** resolved during the v2 migration
**Component:** evaluator (`evaluation/semantic/judge.py`)
**Severity:** high — silently loses a whole assessment and misreports the cause

### Observation

Found while running the first v2 historical replay. `developmental-review` degraded with:

```
JudgeUnavailableError: Judge request failed after 3 attempt(s):
Expecting ',' delimiter: line 1 column 1264 (char 1263)
```

The model had responded, and had responded quickly; it emitted a literal newline inside a
JSON **string value** instead of the `\n` escape. `parse_json_object` tried the text as
returned, then tried slicing the outermost `{...}`, and both failed — so the response was
thrown away and reported as an unavailable judge after three identical retries.

### Why it mattered more than it looked

Two compounding faults:

1. **The response was recoverable.** A single unescaped `\n` inside a string is valid-JSON-
   with-one-character-wrong. The parser had no repair step, so a formatting detail the model
   cannot see cost the entire assessment.
2. **The error named the wrong cause.** "Judge request failed after 3 attempt(s)" reads as a
   connectivity or credential problem, which sends an investigation to the network, the key,
   and the endpoint. The artifact recorded nothing about what the model actually sent, so
   the parse failure was indistinguishable from an outage after the fact.

A third, quieter effect: because the retry loop treats `json.JSONDecodeError` as retryable,
the same malformed request was sent three times at full cost and produced the same result.

### Resolution

* `repair_control_characters` walks the response with a small state machine and escapes raw
  control characters **inside string literals only**, leaving structural whitespace
  untouched. `parse_json_object` now tries: as-returned, repaired, then the brace-sliced
  slice and its repair.
* `DeepSeekJudge.last_raw_content` retains the response, and a final parse failure raises
  with the first 300 characters as received. A parse failure now names itself.
* `evaluation/tests/test_judge_parsing.py` covers the repairs, the cases that must **not** be
  altered (already-escaped newlines, escaped quotes, pretty-printed JSON), and the excerpt.

### Evidence

The same draft that degraded now returns a full review:

```
ok: true | issues: 10
problem types: ["unsupported_connection","overstated_claim","miscalibrated_depth",
                "unexplained_concept","structural_uniformity","unclear_referent",
                "missing_context","unclear_sequence","missing_significance"]
vocabulary source: wops | judge tokens: 30479
```

### What would settle whether it recurs

Any future `JudgeUnavailableError` should be checked against the recorded excerpt before
being treated as an outage. If the excerpt shows well-formed JSON, the parser has a new gap;
if it shows a truncated response, the cause is the output ceiling rather than the parser.

---

## KI-006 — `resume` discarded the earlier stages' audit record

**Status:** resolved during the v2 migration
**Component:** runner (`tools/pipeline/v2.mjs`)
**Severity:** medium — the artifacts and the cost record stayed correct, but the audit trail did not

### Observation

After re-running only the `render` stage of a completed v2 replay, `stage-records.json`
listed one stage instead of ten. The verifier reported the other nine as missing:

```
ERROR stage:analyze: the stage has no record in stage-records.json
ERROR stage:frame: the stage has no record in stage-records.json
...
```

### Why it mattered

`stage-records.json` is the run's per-stage audit: status, provenance, the context manifest,
the corpus projection, and any warnings. A resumed run executes part of the pipeline and then
wrote its own records as the whole file, so the earlier stages' records were replaced by
nothing. Every artifact was still on disk and the cost accounting was unaffected, because
both are read from the attempt directories — which is precisely what made the loss easy to
miss. The record that answers *what did each stage receive, and did it degrade* was gone.

### Resolution

`stage-records.json` is now merged rather than replaced. Executed stages take their new
record; stages that did not re-run keep the record already on disk; warnings are unioned,
because a warning from a stage that did not re-run is still true of the artifact being
described. The file also records the `modes` it has been written in (`run`, `resume`,
`replay`), so a record assembled across several invocations says so.

### Contributing factor: the verifier read the wrong source first

The defect was found because `verify-replay.mjs` reads `stage-records.json` while
`verify-run.mjs` reads the attempt directories. The two disagreeing is what surfaced it. That
disagreement is deliberate and worth keeping: the attempt directories are the primary
artifact, and the record is a derived summary that must therefore be checked against them.

### What would settle whether it recurs

Any resumed v2 run should show the same stage count in `stage-records.json` as the stage list
in `pipeline.json`. A mismatch means a record was lost, not that a stage was skipped — a
skipped stage still has a record, with `status: "skipped"`.
