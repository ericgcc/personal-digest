# Digest state database
This is the runtime contract for persistent Digest System state.

* Database: `state/digest-state.db`
* Engine: SQLite
* Schema version: `1`
* Version check: `PRAGMA user_version = 1`
* Scope: one shared database for every digest

`digest_id` is the state namespace. The same Gmail message or article may therefore be stored once for `medium-bi-daily` and independently for another digest. Do not apply global deduplication across digest IDs.

Digest aliases are **not stored in the database**. They remain configuration in `digests/<digest-id>.md`. Reads use the canonical ID plus declared aliases; all new writes use only the canonical ID.

## Runtime access
Treat the database as binary state, not as a document.

1. Fetch the Drive file as raw bytes to a local working path.
2. Open the local copy with SQLite. Python's standard-library `sqlite3` module is acceptable.
3. On every connection execute:

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
```

Do not use WAL mode for the persisted Drive copy because WAL requires sidecar files that are not part of the configured state artifact.

Before reading state, require:

```sql
PRAGMA integrity_check;      -- must return exactly: ok
PRAGMA foreign_key_check;    -- must return zero rows
PRAGMA user_version;         -- must return: 1
```

Use parameterized SQL for values. Never construct SQL by interpolating email IDs, URLs, titles, digest IDs, or other source data.

## Single-writer rule
The database supports any number of configured digests, but the Drive-backed state artifact has one writer at a time.

* Record the Drive `modifiedTime` when the database is fetched.
* Before replacing the Drive file after a state commit, fetch metadata again.
* If `modifiedTime` changed, do not overwrite it. Re-fetch the newest database and replay the intended transaction against that copy, or stop safely if the merge cannot be proven safe.
* Never create a separate active database per digest to work around concurrency.

This protects the multi-digest state model from lost updates even though Drive is file storage rather than a database server.

## Schema
```sql
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE runs (
    run_key TEXT PRIMARY KEY,
    digest_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    delivered_at TEXT,
    subject TEXT NOT NULL,
    source_email_count INTEGER NOT NULL DEFAULT 0 CHECK (source_email_count >= 0),
    reviewed_item_count INTEGER NOT NULL DEFAULT 0 CHECK (reviewed_item_count >= 0),
    cited_item_count INTEGER NOT NULL DEFAULT 0 CHECK (cited_item_count >= 0),
    notes TEXT
);

CREATE TABLE emails (
    digest_id TEXT NOT NULL,
    gmail_message_id TEXT NOT NULL,
    gmail_thread_id TEXT,
    subject TEXT,
    sender TEXT,
    received_at TEXT NOT NULL,
    adapter TEXT NOT NULL,
    processed_run_key TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (digest_id, gmail_message_id),
    FOREIGN KEY (processed_run_key)
        REFERENCES runs(run_key) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE items (
    digest_id TEXT NOT NULL,
    item_key TEXT NOT NULL,
    canonical_url TEXT,
    title TEXT NOT NULL,
    author_or_publication TEXT,
    source_message_id TEXT NOT NULL,
    adapter TEXT NOT NULL,
    review_status TEXT NOT NULL,
    first_reviewed_at TEXT NOT NULL,
    last_run_key TEXT NOT NULL,
    PRIMARY KEY (digest_id, item_key),
    FOREIGN KEY (last_run_key)
        REFERENCES runs(run_key) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (digest_id, source_message_id)
        REFERENCES emails(digest_id, gmail_message_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX idx_runs_digest_delivered
    ON runs(digest_id, delivered_at);
CREATE INDEX idx_emails_digest_processed
    ON emails(digest_id, processed_at);
CREATE INDEX idx_emails_run
    ON emails(processed_run_key);
CREATE INDEX idx_items_digest_reviewed
    ON items(digest_id, first_reviewed_at);
CREATE INDEX idx_items_run
    ON items(last_run_key);
CREATE INDEX idx_items_source_message
    ON items(digest_id, source_message_id);
CREATE UNIQUE INDEX uq_items_digest_canonical_url
    ON items(digest_id, canonical_url)
    WHERE canonical_url IS NOT NULL AND canonical_url <> '';
```

The database must also set `PRAGMA user_version = 1`.

`items.review_status` stores the final editorial or operational outcome for an item. Keep existing historical values readable, including `not_selected`, but new runs must write `reviewed` for a substantively reviewed ordinary omission. Stable lower-snake-case values may include reader-facing editorial outcomes such as `selected`, `reviewed`, `worth_reading`, and `limited_content`, plus internal operational outcomes such as `duplicate`, `email_only`, `promotional_content`, `administrative`, `social_notification`, `low_signal`, `inaccessible`, or `excluded_before_read` when needed for deduplication and accountability.

Reader-facing catalog eligibility is separate from state retention. Internal operational outcomes never require a source number or rendered catalog row. `email_only` is normally provenance attached to an editorial outcome rather than a competing selection class. When a historical `not_selected` value must be shown for a catalog-eligible substantive item, render it as `Reviewed`; do not rewrite history merely to change the label. The special value `worth_reading` is permitted only for `curated-discovery` and `synthesis-max`, only when the source was **not** selected into the editorial body, and corresponds to their yellow source-catalog recommendation. It is not a Discovery classification. Any source represented in the editorial body must be stored as `selected`, never `worth_reading`.

## State lookup
Build a read-identity list containing the canonical digest ID followed by any declared aliases.

### Email already processed
Query `emails` for the Gmail message ID under any read identity. A match means the email must not be reprocessed for the current digest.

Conceptually:

```sql
SELECT digest_id, gmail_message_id, processed_run_key
FROM emails
WHERE digest_id IN (<canonical-id-and-aliases>)
  AND gmail_message_id = ?
LIMIT 1;
```

### Item already reviewed
Prefer `item_key`. Also use a normalized canonical URL when available so tracking variants do not create duplicate state.

```sql
SELECT digest_id, item_key, canonical_url, review_status, last_run_key
FROM items
WHERE digest_id IN (<canonical-id-and-aliases>)
  AND (
        item_key = ?
        OR (? IS NOT NULL AND canonical_url = ?)
      )
LIMIT 1;
```

Normalize missing or empty canonical URLs to SQL `NULL` before writes.

### Run already delivered
```sql
SELECT run_key, digest_id, status, delivered_at
FROM runs
WHERE run_key = ?
LIMIT 1;
```

A matching deterministic run key prevents duplicate delivery.

## Commit after successful delivery
Do not persist a run as processed before Gmail confirms delivery.

After successful delivery, apply all state changes to the local database in one transaction:

```sql
BEGIN IMMEDIATE;
-- insert the delivered run
-- insert every admitted email
-- insert every reviewed item
COMMIT;
```

The expected order is `runs` -> `emails` -> `items` so foreign-key relationships are satisfied.

For normal execution, unexpected primary-key or unique-key conflicts are errors, not permission to silently overwrite prior state. During an explicit repair after a confirmed sent email, inspect existing rows and insert only genuinely missing state; never rewrite unrelated history just to make the transaction succeed.

After commit:

1. run `PRAGMA integrity_check` and `PRAGMA foreign_key_check` again;
2. close the SQLite connection completely;
3. verify the Drive database has not changed since download;
4. replace the same `state/digest-state.db` Drive file with the committed local copy;
5. only then apply the canonical `Digest/Processed/<digest-id>` Gmail labels.

If database persistence succeeds but Gmail labeling fails, the database remains authoritative for deduplication and the labels can be repaired later. If Gmail delivery succeeds but database persistence fails, do not send again; use the deterministic run key plus Gmail Sent evidence to repair missing database state on the next execution.

## Historical migration
The initial SQLite database was migrated from `state/Digest Processing Ledger.xlsx` without rewriting historical digest IDs. Historical `medium-daily` rows therefore remain `medium-daily`; the current digest config's alias makes that state visible to `medium-bi-daily` reads. New writes use only `medium-bi-daily`.
