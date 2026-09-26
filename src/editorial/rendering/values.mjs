// Authoritative rendering values: the run key and the deterministic template values.

import { wordCount, splitCatalog } from "../validation/copy-verify.mjs";

/**
 * Resolve the authoritative run key for a run.
 *
 * Order: the orchestrator's precomputed marker, then the corpus `run_key`, then a
 * deterministic derivation from the digest ID and the sorted admitted Gmail message
 * IDs — the same rule `system/workflow.md` states. Deriving it keeps a replay's
 * duplicate-delivery guard meaningful instead of empty.
 */
export function resolveRunKey({ corpus, digestId, style }) {
  const marker = corpus?.delivery?.invisible_html_run_marker;
  if (typeof marker === "string") {
    const extracted = /run-key:\s*(.+?)\s*-->/.exec(marker)?.[1]?.trim();
    if (extracted) return { runKey: extracted, source: "delivery.invisible_html_run_marker" };
  }
  if (typeof corpus?.run_key === "string" && corpus.run_key.trim()) {
    return { runKey: corpus.run_key.trim(), source: "corpus.run_key" };
  }
  const messageIds = [];
  for (const source of Array.isArray(corpus?.sources) ? corpus.sources : []) {
    const value = source?.originating_gmail_message_id;
    if (value) messageIds.push(String(value));
  }
  for (const email of Array.isArray(corpus?.source_emails) ? corpus.source_emails : []) {
    const value = email?.originating_gmail_message_id;
    if (value) messageIds.push(String(value));
  }
  const unique = [...new Set(messageIds)].sort();
  return {
    runKey: `${digestId}-${style}-${unique.join("+") || "no-messages"}`,
    source: "derived:digest+sorted-message-ids",
  };
}

//: Minutes-per-word basis for estimating the digest's own reading time, stated by
//: `system/workflow.md` and `system/html-rendering.md`. It is a shared assumption, not a
//: per-style setting.
const WORDS_PER_MINUTE = 225;

//: Outcome wording that means the item was *not* substantively read. The corpus's `sources`
//: array already contains only catalog-eligible substantively reviewed items — inaccessible
//: and pre-filtered material lives in `pending_items` and `operational_exclusions` — but a
//: recorded outcome can still contradict that, so it is checked rather than assumed. The
//: set is matched loosely because the value is free text written by the acquisition stage.
const NON_SUBSTANTIVE_OUTCOMES = [
  "not_read", "unread", "not_selected", "skipped", "duplicate", "inaccessible",
  "excluded", "pending", "discarded", "unsupported", "not_available",
];

function isSubstantivelyRead(source) {
  const outcome = String(source?.reading_outcome ?? "").trim().toLowerCase();
  if (!outcome) return true; // no claim either way; the corpus listing is the claim
  return !NON_SUBSTANTIVE_OUTCOMES.some((marker) => outcome.includes(marker));
}

/**
 * Resolve every authoritative value the rendering template needs.
 *
 * The render stage is a presentation layer: it must not invent a date, a reading time, or a
 * digest name, and it must not derive the time-saved capsule itself. Those values are
 * deterministic here, so the runner computes them and supplies them, exactly as it does the
 * run key. Every value carries its source so an audit can tell a measured number from a
 * derived one, and a value that genuinely cannot be resolved is omitted rather than guessed.
 */
export function resolveRenderingValues({ corpus, digestId, digestName, style, language, bodyProse }) {
  const values = {
    digest_id: digestId,
    digest_name: digestName ?? null,
    style,
    language,
  };
  const notes = [];

  // --- html lang ---------------------------------------------------------------------
  // Some corpora record the resolved BCP 47 tag during acquisition. When they do, that value
  // is authoritative and is passed through. When they do not, resolving it is a localization
  // decision, which `system/html-rendering.md` assigns to the rendering stage.
  const declaredHtmlLang = typeof corpus?.html_lang === "string" ? corpus.html_lang.trim() : "";
  if (declaredHtmlLang) {
    values.html_lang = declaredHtmlLang;
    values.html_lang_source = "corpus.html_lang";
  } else {
    values.html_lang_instruction = "Resolve a valid BCP 47 tag for <html lang> from the declared language above.";
  }

  // --- date -------------------------------------------------------------------------
  // `delivery.subject` is the orchestrator's authoritative localized subject, and it carries
  // the digest date. The ISO fact behind it comes from the corpus's acquisition time. Both
  // are supplied: the fact, and an example of it already localized, so the rendering stage
  // formats the date for the target language rather than translating an English one.
  const subject = typeof corpus?.delivery?.subject === "string" ? corpus.delivery.subject.trim() : null;
  if (subject) {
    values.delivery_subject = subject;
    values.date_source = "delivery.subject";
  }
  const acquired = corpus?.acquisition_time;
  const acquiredAt = typeof acquired === "string" ? new Date(acquired) : null;
  if (acquiredAt && !Number.isNaN(acquiredAt.getTime())) {
    values.date_iso = acquiredAt.toISOString().slice(0, 10);
    values.date_source = values.date_source ?? "corpus.acquisition_time";
  } else {
    // Some corpora record no acquisition time. The latest received timestamp among the
    // sources is the same fact arrived at differently, and a digest dated by when its newest
    // source arrived is honest in a way that today's date is not.
    const received = (Array.isArray(corpus?.sources) ? corpus.sources : [])
      .map((source) => new Date(source?.received_at ?? ""))
      .filter((date) => !Number.isNaN(date.getTime()))
      .sort((a, b) => b.getTime() - a.getTime());
    if (received.length) {
      values.date_iso = received[0].toISOString().slice(0, 10);
      values.date_source = values.date_source ?? "latest source received_at";
    } else if (subject) {
      // The subject is authoritative and already localized, but it is a sentence rather than
      // a value. Extracting the date from it is a locale-aware reading task, and guessing at
      // it here with a date parser would be worse than saying so. This is *guidance* — the
      // value is available, just not in machine-readable form — so it is not a warning.
      values.date_instruction =
        "The digest date is inside the authoritative delivery subject above. Take it from there " +
        "rather than formatting a date independently, and reuse the subject's own localization.";
    } else {
      notes.push("No digest date could be resolved: the corpus carries no delivery subject, acquisition time, or source timestamps.");
    }
  }

  // --- reading time -----------------------------------------------------------------
  const sources = Array.isArray(corpus?.sources) ? corpus.sources : [];
  let sourceMinutes = 0;
  let counted = 0;
  for (const source of sources) {
    if (!isSubstantivelyRead(source)) continue;
    const minutes = Number(source?.reading_time_minutes ?? source?.reading_minutes ?? 0);
    if (!Number.isFinite(minutes) || minutes <= 0) continue;
    sourceMinutes += minutes;
    counted += 1;
  }
  if (counted > 0) {
    values.reviewed_source_minutes = Number(sourceMinutes.toFixed(1));
    values.reviewed_source_count = counted;
    values.reviewed_source_basis = "sum of recorded reading times for substantively read sources";
  } else {
    notes.push(
      "No reviewed-source reading time could be resolved: no source records a substantive reading outcome with a reading time. " +
      "The capsule must use the contract's degraded digest-only form rather than a partially filled source → digest pair.",
    );
  }

  // --- the digest's own reading time, and the saving ---------------------------------
  const words = wordCount(splitCatalog(bodyProse ?? "").body);
  if (words > 0) {
    values.digest_body_words = words;
    values.digest_minutes = Number((words / WORDS_PER_MINUTE).toFixed(1));
    values.digest_minutes_basis = `${words} body words at ${WORDS_PER_MINUTE} words per minute, excluding the source catalog`;
    if (values.reviewed_source_minutes !== undefined) {
      const saved = values.reviewed_source_minutes - values.digest_minutes;
      if (saved > 0) {
        values.time_saved_minutes = Number(saved.toFixed(1));
      } else {
        notes.push("The reviewed-source total is not longer than the digest, so no time saved can be stated.");
      }
    }
  } else {
    notes.push("The approved prose was unavailable, so the digest reading time could not be computed.");
  }

  return { values, notes };
}

/**
 * The two reading-time halves of the capsule, plus the saving.
 *
 * Returned separately so each half's basis is explicit: the source total is a sum over the
 * corpus and the digest total is derived from the approved prose. Neither is a guess, and a
 * half that cannot be resolved stays absent rather than becoming a fabricated number — the
 * rendering contract has a defined degraded form for exactly that case.
 */
export function describeReadingTime(values) {
  return {
    reviewed_source_minutes: values.reviewed_source_minutes ?? null,
    reviewed_source_count: values.reviewed_source_count ?? null,
    digest_body_words: values.digest_body_words ?? null,
    digest_minutes: values.digest_minutes ?? null,
    time_saved_minutes: values.time_saved_minutes ?? null,
  };
}