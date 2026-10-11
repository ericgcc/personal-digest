# Spec Delta

## Purpose

Integrate the WOPS anti-pattern catalogue into the editorial pipeline so common writing defects are prevented before drafting, detected in the draft with WOPS's own signals, repaired through targeted operation selection, and independently verified after revision — without adding stages, judge calls, or duplicated catalog data.

## ADDED Requirements

### Requirement: Anti-pattern catalogue is sourced from WOPS

The system SHALL obtain anti-pattern definitions exclusively through the digest system's WOPS adapter (`WopsAdapter` in `digest_system/integrations/wops.py`), whose wrapper methods (`list_anti_patterns`, `get_anti_patterns`, `get_writing_operations`, `search_writing_operations`) are adapter-owned names backed by the WOPS CLI (`antipatterns`, `show-antipattern <id> --json`, `show <id> --json`, `search ... --json`); the system SHALL NOT call the WOPS Python API (`WritingOperationsLibrary`) directly, and its differently-named methods (`list_antipatterns`, `get_antipatterns`, `get_operations`) SHALL NOT be assumed to exist under the adapter's names. The system SHALL NOT embed anti-pattern definitions, detection signals, or false-positive conditions as static data, and SHALL NOT hardcode the catalogue's size: the active set is discovered dynamically at run time (16 entries at planning time; the count is not a constant). WOPS loads anti-patterns from its YAML files, so the configured `WOPS_ROOT` SHALL be a local filesystem path to a WOPS checkout (or synchronized copy) that the adapter's subprocess can read; a URL is not a valid root. The run record SHALL state the catalogue's availability and version for every run.

#### Scenario: The adapter contract is verified against WOPS

- **WHEN** the integration's contract tests run against a real WOPS checkout
- **THEN** the adapter's wrapper methods return the catalogue records the WOPS CLI emits, and the test fails if the WOPS interface changes

#### Scenario: Catalogue is available

- **WHEN** a run starts with a configured, reachable WOPS project at a local filesystem path
- **THEN** the run record reports the catalogue as available with the WOPS project version, the discovered active anti-pattern count is whatever WOPS currently provides, and anti-pattern guidance and detection derive from records fetched through the adapter

#### Scenario: Catalogue is unavailable

- **WHEN** the WOPS project is unconfigured, missing, its root is not a readable local path, or its anti-pattern CLI calls fail
- **THEN** the run records the unavailability with the adapter's reason, prevention and detection degrade to the pre-integration behavior, and the pipeline completes without error

### Requirement: Draft receives bounded preventive anti-pattern guidance

The Draft stage SHALL receive a compact preventive guidance block derived from the WOPS anti-pattern catalogue. The block SHALL contain a small, relevant subset selected using WOPS record metadata (including `activities[]`), bounded by a fixed maximum entry count and a configurable byte budget enforced in code, with the block's size recorded in the prompt manifest. Each included entry SHALL be complete (name, one-sentence summary, and false-positive conditions) and SHALL NOT be truncated mid-entry; when the budget is exhausted, lower-priority entries SHALL be omitted whole and the omitted count SHALL be recorded. The block SHALL NOT contain complete detection-signal lists, examples, or provenance. The subset SHALL be selected from the dynamically discovered catalogue, not from a hardcoded entry list.

#### Scenario: Guidance is compact and measured

- **WHEN** a Draft prompt is composed with WOPS available
- **THEN** the prompt manifest records the anti-pattern guidance block with its byte size, and the block stays within the enforced bound

#### Scenario: Selection uses WOPS metadata

- **WHEN** the prevention subset is selected from the catalogue
- **THEN** entries relevant to drafting (per WOPS `activities[]` metadata) are preferred, and the selection is recorded

#### Scenario: Budget exhaustion omits whole entries

- **WHEN** the byte budget is exhausted before all selected entries fit
- **THEN** the remaining entries are omitted whole, no entry is cut mid-sentence, and the omitted count is recorded

#### Scenario: Guidance preserves legitimate devices

- **WHEN** the guidance mentions a defect pattern that resembles a legitimate device (for example a real contrast, a genuine ordinal range, or a required formal conclusion)
- **THEN** the guidance also carries the corresponding false-positive condition, so the writer is not told to avoid the device itself

#### Scenario: Draft proceeds without WOPS

- **WHEN** the catalogue is unavailable at Draft time
- **THEN** the Draft prompt is composed without the guidance block, the omission is recorded, and drafting completes normally

### Requirement: Preventive guidance preserves legitimate devices

No guidance line SHALL prohibit a rhetorical device outright: every line must be conditioned on the defect pattern, and the guidance SHALL carry the false-positive conditions that keep legitimate devices legitimate.

#### Scenario: Guidance preserves legitimate devices

- **WHEN** the guidance mentions a defect pattern that resembles a legitimate device (a real contrast, a genuine ordinal range, a required formal conclusion)
- **THEN** the guidance also carries the corresponding false-positive condition, so the writer is not told to avoid the device itself

### Requirement: Developmental Review detects anti-patterns in the draft

The developmental-review evaluation SHALL, in its existing single judge call, additionally report anti-pattern findings, each carrying the canonical WOPS anti-pattern id, the section it occurs in, a severity, and a one-sentence evidence statement. The judge SHALL receive a bounded projection of each anti-pattern's id, summary, detection signals, and false-positive conditions, so detection is grounded in WOPS's own definitions rather than the judge's general interpretation. Findings are additive; the existing developmental assessment SHALL be unchanged in shape and meaning.

#### Scenario: The judge receives detection signals

- **WHEN** the catalogue is available at review time
- **THEN** the judge's prompt carries each anti-pattern's id, summary, detection signals, and false-positive conditions, bounded in size and recorded in the prompt audit

#### Scenario: A located finding is reported

- **WHEN** the draft contains a passage matching an anti-pattern's detection signals and no false-positive condition applies
- **THEN** the review JSON contains an anti-pattern finding with that anti-pattern's canonical id, the section id, a severity, and evidence text

#### Scenario: A false positive is not reported

- **WHEN** a passage matches a detection signal but the record's false-positive condition applies
- **THEN** the review reports no anti-pattern finding for that passage, or records the false-positive consideration in the finding's evidence

#### Scenario: Existing diagnoses are preserved

- **WHEN** the review runs with anti-pattern detection enabled
- **THEN** the response still contains the existing `issues`, `frame_obligations_missed`, `revision_priorities`, and `dimensions` fields with their current semantics, and no additional judge request is issued

#### Scenario: Detection degrades gracefully

- **WHEN** the catalogue is unavailable at review time
- **THEN** the review completes with no anti-pattern findings and a recorded note, and the existing diagnoses are unaffected

### Requirement: Repair selection honours anti-pattern relationships

The writing-operation retrieval SHALL additionally select operations for anti-pattern findings: each finding's anti-pattern `repair` list supplies candidate operation ids retrieved through the existing WOPS adapter, and an empty `repair` list SHALL produce no selection with the deletion meaning recorded.

#### Scenario: Repair list is honoured

- **WHEN** a finding names an anti-pattern whose `repair` list contains operation ids
- **THEN** the retrieval record shows those ids as candidates selected for that finding, fetched through the adapter

#### Scenario: Empty repair list

- **WHEN** a finding names an anti-pattern whose `repair` list is empty
- **THEN** no operation is selected for it and the record states the repair is deletion

#### Scenario: Retrieval degrades gracefully

- **WHEN** WOPS is unavailable or a repair-list operation cannot be fetched
- **THEN** the record carries the warning, the revision proceeds on reviewer feedback alone, and no error is raised

### Requirement: Overuse risks and severity priority are recorded

Operations named by an anti-pattern's `overuse_of` list SHALL be flagged as overuse risks for the corresponding finding, and when the selection is capped, operations for critical and major findings SHALL be preferred over minor ones.

#### Scenario: Overuse risk is recorded

- **WHEN** a selected operation appears in an anti-pattern's `overuse_of` list
- **THEN** the record marks that operation as an overuse risk for the corresponding finding

#### Scenario: Substantive problems win the cap

- **WHEN** the combined candidate set exceeds the retrieval limit
- **THEN** operations for critical and major findings are preferred over operations for minor findings, and the dropped candidates remain visible in the record

### Requirement: Writer Revision applies diagnoses without becoming a template

The Writer Revision stage SHALL receive the anti-pattern findings and the selected operations in its existing data blocks and SHALL repair the diagnosed problems within its existing single call, under its unchanged Naturalness Contract, evidence fidelity, explanatory completeness, citations, and source attribution obligations. Anti-pattern avoidance SHALL NOT be imposed as an inflexible writing template.

#### Scenario: Diagnoses reach the revision

- **WHEN** Writer Revision's prompt is composed with anti-pattern findings present
- **THEN** the findings and the selected operations appear in the stage's data blocks, with each operation traceable to the finding that selected it

#### Scenario: Revision stays evidence-bounded

- **WHEN** the revision repairs an anti-pattern finding
- **THEN** the repair uses only the approved evidence and preserves citations, source attribution, and the Naturalness Contract's invariants

#### Scenario: No template enforcement

- **WHEN** the revision instructions mention anti-patterns
- **THEN** they direct repairing diagnosed defects and respect false-positive conditions, and do not prescribe a mandatory prose formula or forbid a device outright

### Requirement: Reader Review verifies anti-pattern outcomes

The reader-review evaluation SHALL, in its existing single absolute judge call, receive both the previously diagnosed findings and the compact WOPS detection catalogue (detection signals and false-positive conditions), independently assess the revised prose for anti-pattern occurrences, and report each previously diagnosed finding's outcome as resolved, partially resolved, or still present with location and evidence. The existing absolute assessment SHALL be unchanged in shape and meaning.

#### Scenario: The judge receives the detection catalogue

- **WHEN** the catalogue is available at review time
- **THEN** the judge's prompt carries the compact detection catalogue with false-positive conditions in addition to the prior findings

#### Scenario: A resolved finding is recorded

- **WHEN** a previously diagnosed anti-pattern no longer occurs in the revised prose
- **THEN** the review records that finding's outcome as resolved

#### Scenario: A remaining finding is recorded

- **WHEN** a previously diagnosed anti-pattern still occurs in the revised prose
- **THEN** the review records the outcome as still present with location and evidence

#### Scenario: A new overuse defect is detected

- **WHEN** the revision introduced a new anti-pattern occurrence consistent with overusing a supplied operation
- **THEN** the review reports it as a new finding with the anti-pattern id and evidence

#### Scenario: A new defect not previously diagnosed is detected

- **WHEN** the revised prose contains an anti-pattern occurrence that was not among the previously diagnosed findings
- **THEN** the review reports it as a new finding with the anti-pattern id, location, and evidence, detected by the same signals and false-positive conditions

### Requirement: Verification preserves the existing review and repair behavior

The reader-review verification SHALL NOT add a judge call, and the existing conditional Targeted Repair behavior SHALL be unchanged: it remains optional, at most once, and limited to actionable major/critical problems.

#### Scenario: Verification adds no judge call

- **WHEN** the reader review runs with anti-pattern verification
- **THEN** exactly one judge request is issued for the revised artifact, as before

#### Scenario: Targeted Repair stays conditional

- **WHEN** the review reports anti-pattern outcomes
- **THEN** Targeted Repair still runs only for an actionable major/critical problem and at most once, and anti-pattern bookkeeping alone never triggers it

### Requirement: Score comparability is demonstrated, not assumed

The reader-quality evaluation identity SHALL be preserved across the change only if the scored rubric remains materially equivalent after the verification instructions are added; the equivalence SHALL be validated with representative cases before any historical comparison is used as evidence. If the new instructions materially change score behavior, the evaluation SHALL use a new identity or cross-version scores SHALL be explicitly marked incomparable, and no replay comparison SHALL claim improvement across an incomparable pair.

#### Scenario: Equivalence is validated before comparison

- **WHEN** the verification instructions are added to the reader review
- **THEN** representative cases are evaluated before and after the change, and the recorded evidence shows whether scores remain materially equivalent

#### Scenario: Incomparable scores are never compared

- **WHEN** the validation shows the score behavior materially changed
- **THEN** the evaluation identity changes or the cross-version pair is marked incomparable, and replay comparisons refuse to compute a delta across it

### Requirement: Anti-pattern findings are traceable by stable identifier

Every anti-pattern finding SHALL carry a stable `finding_id`, assigned when the finding is first reported and reused by later stages, so repeated occurrences of the same anti-pattern remain trackable across revision even when sections are reordered or renamed. An anti-pattern id plus section id alone SHALL NOT be relied on as a unique key.

#### Scenario: A finding keeps its identity across revision

- **WHEN** a finding diagnosed in the draft is rechecked in the revised prose after sections were reordered
- **THEN** the outcome record references the same `finding_id` as the original diagnosis

### Requirement: The application audit uses explicit observation states

The run artifacts SHALL record, without introducing a new artifact family, an explicit audit vocabulary for each selected operation: `selected` (WOPS recommended it), `supplied` (Writer Revision received its instructions), `application` (applied, not applied, or unknown — recorded only when supported by evidence), and `outcome` (Reader Review's assessment of the resulting text). Application SHALL NOT be inferred automatically from a resolved anti-pattern, because the model may have corrected the defect another way.

#### Scenario: The audit vocabulary is recorded

- **WHEN** a run completes with WOPS available and findings detected
- **THEN** each selected operation's record states its `selected`, `supplied`, `application`, and `outcome` observations, keyed by `finding_id`

#### Scenario: Application is not claimed without evidence

- **WHEN** an operation was supplied to Writer Revision but no evidence establishes that it was applied
- **THEN** the record states `application: unknown` rather than applied, even if the anti-pattern was later reported resolved

#### Scenario: A resolved anti-pattern does not imply the operation was used

- **WHEN** the Reader Review outcome shows an anti-pattern resolved after an operation was supplied for it
- **THEN** the record shows the outcome as resolved and the application as whatever the evidence supports, without equating resolution with application
