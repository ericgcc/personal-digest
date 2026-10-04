# Builder Brief — Iteration 2 (CLOSED EDIT LIST)

The Inspector returned FAIL with three issues. This brief is a **closed list**.
Do NOT search the repository. Do NOT read files other than the ones named here.
Make exactly these edits, then run the gates.

## Hard rules

1. **Do not explore.** No `grep`, no `file_search`, no reading files not listed here.
2. **Do not run the full test suite until the end.** Run it once, at step 7.
3. Use `C:\Users\ericg\.conda\envs\digest-eval\python.exe` for Python.
4. Never bulk-edit with PowerShell `Set-Content`/`Get-Content -Raw`. Use the edit tools.
5. Do not leave scratch files in the repo root.

## The new topology (reference)

`analyze, frame, draft, developmental-review, writer-revision, copy-edit,
reader-review, targeted-repair, publication-verify, render`

- `copy-edit` — artifact `copy-edit.md`, corpus `none`, executor `llm`.
- `publication-verify` — artifact `final.md`, corpus `provenance`, executor
  `deterministic`, extra artifact `verification.json`.
- Reader Review compares Writer Revision (BEFORE) → Copy Edit (AFTER).

---

## Edit 1 — `system/workflow.md`

Replace the stage table rows (around lines 400–403). The current rows are:

```
| `line-edit` | `revision.md` + `wops.json` | `line-edit.md` | `LINE EDIT`: clarity, voice, naturalness, rhythm, transitions, redundancy, concision, and length in one pass. |
| `reader-review` | `revision.md` (BEFORE) + `line-edit.md` (AFTER) | `review.json` | `READER REVIEW`: assess the later prose absolutely and detect any material regression, with targeted retry instructions. |
| `targeted-repair` | `line-edit.md` + reader feedback + `wops.json` | `repair.md` | `TARGETED REPAIR`: **optional, at most once.** Repair one diagnosed reader problem, or skip. |
| `copy-verify` | current prose + source provenance | `final.md` + `verification.json` | `COPY & VERIFY`: deterministic publication checks first, then copy correction only. Must not rewrite editorially. |
```

Replace with:

```
| `copy-edit` | `revision.md` + `wops.json` | `copy-edit.md` | `COPY EDIT`: detailed copyediting — clarity, grammar, syntax, spelling, punctuation, terminology consistency, local redundancy, naturalness, rhythm, awkward phrasing, minor local rewording, citation preservation, and heading/terminology consistency. It may not significantly restructure the document. |
| `reader-review` | `revision.md` (BEFORE) + `copy-edit.md` (AFTER) | `review.json` | `READER REVIEW`: assess the copy-edited prose as a reader, and detect anything the copy edit materially regressed. |
| `targeted-repair` | `copy-edit.md` + reader feedback + `wops.json` | `repair.md` | `TARGETED REPAIR`: **optional, at most once.** Repair one diagnosed reader problem, or skip. |
| `publication-verify` | current prose + source provenance | `final.md` + `verification.json` | `PUBLICATION VERIFY`: run the deterministic publication checks over the revised prose and produce an auditable report. It never edits prose. |
```

Also in the same file:

- Line ~406: change `the current `developmental-review`, `writer-revision`, `line-edit`, and `copy-verify` contracts` to `the current `developmental-review`, `writer-revision`, `copy-edit`, and `publication-verify` contracts`.
- Line ~424: change the `provenance` corpus row's stage from `copy-verify` to `publication-verify`.
- Line ~425: change the `none` corpus row's stage list from `frame`, `developmental-review`, `line-edit`, `reader-review`, `targeted-repair`, `render` to `frame`, `developmental-review`, `copy-edit`, `reader-review`, `targeted-repair`, `render`.
- Line ~448: change `produced `final.md` from `copy-verify`` to `produced `final.md` from `publication-verify``, and `The `copy-verify` stage also writes` to `The `publication-verify` stage also writes`.

## Edit 2 — `docs/architecture/editorial-process.md`

- Line ~10: change the pipeline string to
  `SELECT → ANALYZE → FRAME → DRAFT → DEVELOPMENTAL REVIEW → WRITER REVISION → COPY EDIT → READER REVIEW → [TARGETED REPAIR] → PUBLICATION VERIFY`.
- Line ~134: change the heading `## 7. LINE EDIT—make the prose work` to `## 7. COPY EDIT—make the prose work`.
- Line ~156: change `Line edit may not change` to `Copy edit may not change`.
- Line ~164: change `Did the line edit materially regress` to `Did the copy edit materially regress`.
- Line ~175: change `the line-edited prose is used` to `the copy-edited prose is used`.
- Line ~177: change the heading `## 10. COPY & VERIFY—publication check` to `## 10. PUBLICATION VERIFY—publication check`.
- Also update the sentence near the top that says `Each stage's responsibilities, inputs, and constraints are stated in its contract under `system/contracts/`.` to say `under `editorial/stages/`.`

## Edit 3 — `docs/guides/usage.md`

- Line ~42: change `--from-stage line-edit` to `--from-stage copy-edit`.

## Edit 4 — `rendering/shared.md`

- Line ~161: delete the bullet `* `detailed` keeps each source independently identifiable inside its own entry and has no source catalog.`
- Line ~162: delete the bullet `* `concise` uses the source/publication label plus the article/item title and has no source catalog.`

(These describe removed styles. Keep the surrounding `synthesis-max` / `curated-discovery` bullets.)

## Edit 5 — `system/html-rendering.md`

This file is a stale duplicate of `rendering/shared.md` and is referenced by no runtime
code. **Delete it** (`git rm system/html-rendering.md`).

## Edit 6 — remove the out-of-scope templates

```
git rm templates/concise-email-v1.html templates/detailed-email-v1.html
```

## Edit 7 — `docs/architecture/overview.md`

Add a short section naming the ten-stage workflow in order, so `docs/architecture/`
states the final topology. Use the list from "The new topology" above. Keep it brief
(one paragraph plus the ordered list).

---

## Gates (run once, at the end)

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest -q
C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\prompt_migration_gate.py --json
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --check
```

If a gate fails, fix only the named cause, then re-run that one gate.

## Commit

Single commit: `docs(editorial): [B] finish phase 2 doc and template cleanup`
(≤72 chars). Trailer: `Assisted-by: DeepSeek:DeepSeek V4.1 Flash`.