"""The versioned G-Eval definition for reader-facing editorial quality.

Everything here is part of the evaluation definition and is versioned in
:mod:`evaluation.version`. Changing the steps, the rubric, or the reader task
changes the meaning of every historical score, so all three are recorded with
each result.

The judge is deliberately *not* given the source articles. This metric measures
the experience of a reader who has not read the sources; if the judge could see
them it would silently fill in context the digest itself failed to provide.
"""

from __future__ import annotations

from deepeval.metrics.g_eval import Rubric

from ..version import METRIC_NAME

#: The ``input`` given to the G-Eval test case: the reader's task, not a source.
READER_TASK_DESCRIPTION = (
    "Read the digest stage output below as an intelligent reader who has not read "
    "any of the source articles it was built from. Judge how well the output "
    "explains its subject, situation, and main point, and how strong the reader's "
    "actual understanding of the text is after one careful read."
)

#: Explicit evaluation steps. These are supplied rather than generated so the
#: definition is stable and auditable across historical runs.
EVALUATION_STEPS: tuple[str, ...] = (
    "Read the output as an intelligent reader who has not seen any of the source "
    "material. Determine whether the subject, the situation, and the main point "
    "are understandable on the first read.",
    "Check whether technical concepts, actors, references, examples, and causal "
    "relationships receive enough context to understand why they are being "
    "mentioned. Penalize unexplained referents and statements that only make "
    "sense if the reader already knows the source.",
    "Determine whether the text explains and synthesizes ideas rather than merely "
    "paraphrasing, enumerating, or reporting what individual sources said.",
    "Evaluate the progression of the argument or narrative. Each paragraph should "
    "establish enough context for the next one, and relationships such as cause, "
    "contrast, consequence, or significance should be explicit when necessary.",
    "Penalize sentences or passages that are grammatically valid but require "
    "rereading to understand. Do not penalize technical subject matter simply "
    "because it is technical if it is explained clearly.",
    "Judge the output in its original language. Do not penalize non-English "
    "writing; the quality standard must remain conceptually equivalent across "
    "languages.",
    "Produce the final score based on the reader's actual ability to understand "
    "the text, not on superficial polish. Strong grammar or elegant wording must "
    "not compensate for missing context or unclear explanation.",
    "Write the reason in English, even when the evaluated digest is written in "
    "another language, so that historical reports remain comparable.",
)

#: Explicit score bands.
#:
#: DeepEval normalizes the raw score onto 0-1 even though the bands are expressed
#: on a 0-10 scale. Each band is also an *inclusive decimal interval*: the judge is
#: told that band ``7-8`` means anything from 7.0 up to 8.9 (see
#: :mod:`evaluation.semantic.template`). The band boundaries stay integers because
#: DeepEval validates ``Rubric.score_range`` as an integer tuple bounded by 0-10.
RUBRIC_BANDS: tuple[tuple[tuple[int, int], str], ...] = (
    (
        (0, 2),
        "Fundamentally unclear: the reader cannot reliably determine what important "
        "portions are about without consulting external context. Important "
        "references, concepts, or relationships are unexplained. The text may "
        "resemble compressed notes or source fragments.",
    ),
    (
        (3, 4),
        "Difficult to follow: the general topic can eventually be inferred, but "
        "important context is missing. Multiple passages require rereading or prior "
        "knowledge. The writing frequently reports facts or claims without "
        "explaining their significance or connection.",
    ),
    (
        (5, 6),
        "Understandable but weakly explained: the main point is understandable, but "
        "there are material clarity problems such as missing context, dense "
        "passages, abrupt transitions, unexplained technical references, or "
        "source-by-source reporting instead of synthesis.",
    ),
    (
        (7, 8),
        "Clear and coherent: the output is understandable on the first read. It "
        "provides enough context, explains technical ideas appropriately, connects "
        "claims logically, and synthesizes information into a coherent explanation. "
        "Minor clarity issues may remain.",
    ),
    (
        (9, 10),
        "Exceptionally clear: the output is immediately understandable, "
        "self-contained, well synthesized, and naturally structured. Technical "
        "material is introduced with exactly the context needed. The reader "
        "understands not only what happened or what the sources say, but why the "
        "ideas matter and how they connect.",
    ),
)

#: A short statement of what the metric measures, used as the metric's criteria.
CRITERIA = (
    "Reader-facing editorial quality: how well a digest stage output explains and "
    "synthesizes its subject for a reader who has not read the underlying sources."
)


def build_rubric() -> list[Rubric]:
    """Return the rubric as DeepEval ``Rubric`` objects."""
    return [
        Rubric(score_range=score_range, expected_outcome=outcome)
        for score_range, outcome in RUBRIC_BANDS
    ]


def band_span(score_range: tuple[int, int], decimal_places: int) -> tuple[float, float]:
    """Return the inclusive decimal span of a band, e.g. ``(7, 8)`` -> ``(7.0, 8.9)``.

    Band ``0-2`` covers 0.0-2.9 and band ``9-10`` covers 9.0-10.0, so the bands
    tile the whole scale without gaps or overlap.
    """
    low, high = score_range
    step = 10 ** (-decimal_places)
    if high >= 10:
        return float(low), 10.0
    return float(low), round(high + 1 - step, decimal_places)


def rubric_as_text(decimal_places: int = 0) -> str:
    """Return the rubric in the notation used by the prompt template.

    With ``decimal_places=0`` the bands render as the canonical integer ranges
    (``7-8``). With decimals the bands render as their real decimal spans
    (``7.0-8.9``), which is what the judge is shown.
    """
    lines = []
    for score_range, outcome in RUBRIC_BANDS:
        if decimal_places <= 0:
            start, end = score_range
            label = f"{start}" if start == end else f"{start}-{end}"
        else:
            low, high = band_span(score_range, decimal_places)
            label = f"{low:.{decimal_places}f}-{high:.{decimal_places}f}"
        lines.append(f"{label}: {outcome}")
    return "\n".join(lines)


__all__ = [
    "CRITERIA",
    "EVALUATION_STEPS",
    "METRIC_NAME",
    "READER_TASK_DESCRIPTION",
    "RUBRIC_BANDS",
    "band_span",
    "build_rubric",
    "rubric_as_text",
]
