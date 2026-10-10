# Synthesis MAX B baseline freeze

Goal 2, Phase 2, step 1: freeze the B comparison baseline before any C replay is compared against it.

This record is committed because `.digest-runs/` is gitignored. The artifacts themselves stay in place; this file pins their identity by SHA-256 so any later change to them is detectable.

## Identity of B

| Item | Value |
|---|---|
| B code commit | `364f826` — Phase 6: controlled historical replays and Synthesis MAX activation (2026-09-27) |
| Pipeline | `editorial-pipeline-v2`, pipeline version `2.1.0` |
| Style profile | `synthesis-max-v1`, profile version `2.0.0` |
| Digest | `tech-bi-daily` |
| Historical corpus | `tech-bi-daily-20260921-1109` (Sept 21 Tech corpus) |

Commit `55f60dc` ("refactor(synthesis-max): [B] simplify stage prompts") carries a `[B]` tag, but it is the **C candidate** in the Goal 2 plan. The `[B]` tag there is a builder-convention label, not the B baseline. Only `364f826` produced the B replays.

## Replay identities

| Label | Run ID | Role |
|---|---|---|
| original | `tech-bi-daily-20260921-1109` | Historical pre-Phase-6 run (pipeline `2.0.0`). Context only. |
| B replay 1 | `tech-bi-daily-20260921-1109-r1` | B baseline, replay 1 |
| B replay 2 | `tech-bi-daily-20260921-1109-r2` | B baseline, replay 2 |

## Model and runtime configuration of B

| Setting | Value |
|---|---|
| Provider | DeepSeek |
| Model | `deepseek-flash` (`digest_system/integrations/deepseek.py`) |
| Per-stage reasoning effort | analyze `high`, frame `high`, draft `high`, writer-revision `high`, line-edit `medium`, targeted-repair `medium`, copy-verify `low` (developmental-review and reader-review are evaluator calls, not effort-tagged) |
| Billing band | peak for both replays (original ran off-peak; see `docs/history/phase6-replay-report.md`) |
| Cost, r1 | $0.394087 actual (`run-summary.json`) |
| Tokens, r1 | total 571,513 (input 318,707; output 252,806; reasoning 189,314) |

## Evaluator identity at B

| Item | Value |
|---|---|
| `EVALUATION_ID` | `reader_quality_v4` |
| `EVALUATION_STEPS_VERSION` | `v4.0-style-diagnostics` |
| `RUBRIC_VERSION` | `v4` |
| `SCHEMA_VERSION` | `v2` |
| Judge | DeepSeek `deepseek-flash`, temperature `0.0` (`evaluation/config.py`) |

The B replays recorded a reader review as a **before/after comparison** (`compare-reader-quality`), not as an absolute score. Those historical scores were produced by the evaluator at `364f826`. Step 4 re-scores B with the final evaluator; the historical scores are preserved, not overwritten.

## Frozen artifact hashes

Each run's full inventory is hashed as `sha256(path NUL sha256(file) LF)` over every file, sorted by path. The key artifacts are hashed individually.

Digests computed on 2026-10-10 from `.digest-runs/`.

### Inventory

| Run | Files | Inventory SHA-256 |
|---|---|---|
| original | 128 | `eba9efc0a3a57a9ae07109610786cfe07b0fb25dee704ea6ef550eb12fd028a3` |
| B replay 1 (r1) | 169 | `6ba83740e4869808c7725d32235e4d7561e563bc31e64d1f26fd05cce6579256` |
| B replay 2 (r2) | 169 | `989b9601fdca3c5679d40a420d920186ab7a3c524e9d45144bab2d071b19042b` |

### Key artifacts, B replay 1 (r1)

| Artifact | Bytes | SHA-256 |
|---|---|---|
| `copy-verify/output/final.md` | 14628 | `a17a8ed00dcbb6e55f333171258d7cb78c48f14ad8f34c06a4b4c3c6f85099e8` |
| `copy-verify/output/verification.json` | 16506 | `e161ffe9fa8c9bcda2a619cfeb6a01a50a6c44552d8efe6195b5b8e0172b8dd0` |
| `render/output/email.html` | 47526 | `0c14a0c10a2ce15cf3c0b20aa0a9db2b3c2bd1b8baad3280e653c9133c532acb` |
| `run-summary.json` | 7131 | `67107a52d72c2e7193f37320b209f91879a48b6f26646d68453b50d9b7d36ed3` |
| `stage-records.json` | 26361 | `9e092939904e8d6723e120e5ede277c7a53bf3cbc68f8dd6c0847caf21d6f9aa` |
| `pipeline.json` | 9865 | `e32266dee6a043aa739d204edad8da411cc52c12591c5c4c2b7467adb645dd35` |
| `frame/output/frame.json` | 32301 | `aa5e1a38a727b3a7b68e9c7643102489e20c548730f6972f82b244be41a519a9` |
| `analyze/output/analysis.json` | 87352 | `7fa9772ad869424de006fe3db652aab9212069e002bfd606ea24c9a2c81717dd` |
| `draft/output/draft.md` | 16381 | `6f052fd9a4d45146a8cffaba1502025d385e1bc08df0b798f0ee9c054ed72596` |
| `developmental-review/output/review.json` | 24835 | `49846fef0f051692771f0f28cf8168a9408b6c3c8c81cbeb178139cebc579456` |
| `writer-revision/output/revision.md` | 15145 | `7ab560632e78c3e94425a11f57ed33e8fba8c17de70499a673d892f277b636c6` |
| `line-edit/output/line-edit.md` | 14618 | `b9d90158f9867d10b01ce77230d1011fbb69c0dfa3f91ca249965f883b0d43b5` |
| `reader-review/reader-review-result.json` | 48256 | `5fdc2ea5a471b47a1be51a16f088ef4e3e52324c1c6534f792c83a8ad4edb65f` |

### Key artifacts, B replay 2 (r2)

| Artifact | Bytes | SHA-256 |
|---|---|---|
| `copy-verify/output/final.md` | 14286 | `c34f3fa845cf8fdbb5fbad4df1c864cb26b636f1a99fd5458c565a2240db0921` |
| `copy-verify/output/verification.json` | 12332 | `980ad6b7cc5ccc11a19f9e2930c9028314fb4402ad4892555c5025d9d2eae053` |
| `render/output/email.html` | 46684 | `f471fb3a6f77e9f2cca75bc621a25560f52ff6690f839bacb39a804d3f654afd` |
| `run-summary.json` | 7154 | `e6c859c74a4f1934cff4e3e057ed17e371519a7b2fa9d2c32fc76406629a103d` |
| `stage-records.json` | 26331 | `b2be35d280c69ca58636875d3e2bbe3978d87137c7f6890f5393574bd5211faa` |
| `pipeline.json` | 9865 | `76412f1eb786153f016be2037d446ca3d2bd50b8207e81421e9050b5f183cec7` |
| `frame/output/frame.json` | 47348 | `2e5aec4107b242515743ed6df9a44299f9a0a90b833d7409e3ebabe7a780c49c` |
| `analyze/output/analysis.json` | 107566 | `7fd6a9ca00d69e4ca57373a733c84310c162dab28717baf632e1626e017274e7` |
| `draft/output/draft.md` | 18516 | `fd400f35d42aa5440e00c282d90ac78b7f2f9b29ca447ca7231db5cf023d8e73` |
| `developmental-review/output/review.json` | 25973 | `1b28028bdfac4c521efbc8595140c7993febe0e2ce24274fc80521033b47bd9f` |
| `writer-revision/output/revision.md` | 14334 | `c6865211074040da4f2b1e2f819c9ac05e5f708a16dea3f47f3375fe642d2b36` |
| `line-edit/output/line-edit.md` | 14286 | `4c3e390772bee0c8498a9f43e17027311a63c7097ac240049a384bb980d9aaa7` |
| `reader-review/reader-review-result.json` | 46012 | `68daac67799944e54e19115d5fbee3bbc079f8c8f35d4de46699f6e7ab76fc76` |

Full hashes for the original run's key artifacts are in the same computation and are reproducible by re-running the hashing over `.digest-runs/tech-bi-daily-20260921-1109`.

## Gotchas recorded for this baseline

- The B replays were produced at `364f826`. Re-running B at HEAD would not reproduce them. The B identity is the artifacts plus the commit, not the current code.
- The executor reads `DEEPSEEK_API_KEY` only from the process environment. It does not load `.env`. Replays must be started with the key exported into the environment.
- A replay that fails before its first model call leaves a partial run directory that blocks re-running the same run ID. Remove the partial directory only after confirming it contains no `model-response.json`.

## Verification

- All hashes computed from the files as they exist on disk at freeze time.
- Inventory counts match the directory listings (128 / 169 / 169 files).
- This record does not change any historical artifact.
