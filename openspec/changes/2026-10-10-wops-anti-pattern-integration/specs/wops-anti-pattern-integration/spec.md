# Spec Delta

## Purpose

Integrate the WOPS anti-pattern catalogue into the editorial pipeline so common writing defects are prevented before drafting, detected in the draft with WOPS's own signals, repaired through targeted operation selection, and independently verified after revision — without adding stages, judge calls, or duplicated catalog data.

## ADDED Requirements

### Requirement: Anti-pattern catalogue is sourced from WOPS

The system SHALL obtain anti-pattern definitions exclusively through the existing WOPS adapter interfaces (`list_anti_patterns`, `get_anti_patterns`) against the configured WOPS project, and SHALL NOT embed anti-pattern definitions, detection signals, or false-positive conditions as static data inside this repository. The run record SHALL state the catalogue's availability and version for every run.

#### Scenario: Catalogue is available

- **WHEN** a run starts with a configured, reachable WOPS project
- **THEN** the run record reports the catalogue as available with the WOPS project version, and anti-pattern guidance and detection derive from records fetched through the adapter

#### Scenario: Catalogue is unavailable

- **WHEN** the WOPS project is unconfigured, missing, or its anti-pattern CLI calls fail
- **THEN** the run records the unavailability with the adapter's reason, prevention and detection degrade to the pre-integration behavior, and the pipeline completes without error

### Requirement: Draft receives bounded preventive anti-pattern guidance

The Draft stage SHALL receive a compact preventive guidance block derived from the WOPS anti-pattern catalogue, bounded by a fixed maximum item count and byte size enforced in code, with the block's size recorded in the prompt manifest. The block SHALL carry each anti-pattern's name, one-sentence summary, and false-positive conditions, and SHALL NOT contain complete detection-signal lists, examples, or provenance.

#### Scenario: Guidance is compact and measured

- **WHEN** a Draft prompt is composed with WOPS available
- **THEN** the prompt manifest records the anti-pattern guidance block with its byte size, and the block stays within the enforced bound

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

The developmental-review evaluation SHALL, in its existing single judge call, additionally report anti-pattern findings, each carrying the canonical WOPS anti-pattern id, the section it occurs in, a severity, and a one-sentence evidence statement. The judge SHALL receive the anti-pattern summaries and false-positive conditions. Findings are additive; the existing developmental assessment SHALL be unchanged in shape and meaning.

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

The reader-review evaluation SHALL, in its existing single absolute judge call, check each previously diagnosed anti-pattern finding against the revised prose and report its outcome as resolved, partially resolved, or still present with location and evidence, applying the same false-positive conditions. The existing absolute assessment SHALL be unchanged in shape and meaning.

#### Scenario: A resolved finding is recorded

- **WHEN** a previously diagnosed anti-pattern no longer occurs in the revised prose
- **THEN** the review records that finding's outcome as resolved

#### Scenario: A remaining finding is recorded

- **WHEN** a previously diagnosed anti-pattern still occurs in the revised prose
- **THEN** the review records the outcome as still present with location and evidence

#### Scenario: A new overuse defect is detected

- **WHEN** the revision introduced a new anti-pattern occurrence consistent with overusing a supplied operation
- **THEN** the review reports it as a new finding with the anti-pattern id and evidence

### Requirement: Verification preserves the existing review and repair behavior

The reader-review verification SHALL NOT add a judge call, and the existing conditional Targeted Repair behavior SHALL be unchanged: it remains optional, at most once, and limited to actionable major/critical problems.

#### Scenario: Verification adds no judge call

- **WHEN** the reader review runs with anti-pattern verification
- **THEN** exactly one judge request is issued for the revised artifact, as before

#### Scenario: Targeted Repair stays conditional

- **WHEN** the review reports anti-pattern outcomes
- **THEN** Targeted Repair still runs only for an actionable major/critical problem and at most once, and anti-pattern bookkeeping alone never triggers it

### Requirement: Anti-pattern integration is auditable in run artifacts

The run artifacts SHALL record, without introducing a new artifact family: the catalogue's availability and version; the detected anti-pattern ids with affected sections, severity, and evidence; the selected repair operation ids with the diagnoses that selected them; and the Reader Review outcomes for previously diagnosed findings. An operation supplied to Writer Revision SHALL NOT be recorded as effective unless the Reader Review outcome or a deterministic check supports it.

#### Scenario: The trail is complete for a run

- **WHEN** a run completes with WOPS available and findings detected
- **THEN** the run's existing artifacts contain the catalogue status, the detected findings, the selected operations with their diagnoses, and the verification outcomes, each traceable by anti-pattern id

#### Scenario: Application is not claimed without evidence

- **WHEN** an operation was supplied to Writer Revision but the Reader Review outcome shows the anti-pattern still present
- **THEN** the record shows the outcome as still present and does not describe the operation as applied or effective
