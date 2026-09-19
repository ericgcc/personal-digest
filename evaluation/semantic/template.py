"""A G-Eval prompt template that permits sub-integer scores.

DeepEval's stock G-Eval template asks the judge for "an integer between 0 and 10".
After DeepEval normalizes the raw value onto 0-1, that makes the smallest
expressible score change 0.10 — which, on the historical corpus, was exactly the
size of the measurement noise. A metric whose resolution equals its noise cannot
report anything.

DeepEval's ``Rubric.score_range`` is validated to integer tuples bounded by 0 and
10, so the score *scale* cannot be widened without breaking normalization
(``score = (raw - start) / span``). The scale is therefore kept at 0-10 and the
*prompt* is changed instead: the judge is asked for a value with one decimal
place inside the band it selects. The raw value stays interpretable by DeepEval
(``7.4`` normalizes to ``0.74``) while the resolution improves tenfold, from 11
possible values to 101.

This module holds the whole prompt, so the scoring instruction is auditable in
one place rather than inherited implicitly from the library.
"""

from __future__ import annotations

from typing import Any

from deepeval.metrics.g_eval.g_eval import GEvalTemplate

from ..version import SCORE_DECIMAL_PLACES

#: How a band range is described to the judge, e.g. ``7-8`` becomes ``7.0-8.9``.
def _band_span_text(low: int, high: int, decimal_places: int) -> str:
    step = 10 ** (-decimal_places)
    top = high + 1 - step
    return f"{low:.{decimal_places}f}-{top:.{decimal_places}f}"


def build_evaluation_prompt(
    *,
    evaluation_steps: str,
    test_case_content: str,
    parameters: str,
    rubric: str | None,
    score_range: tuple[float, float],
    decimal_places: int = SCORE_DECIMAL_PLACES,
    additional_context: str | None = None,
) -> str:
    """Build the G-Eval evaluation prompt with a fractional scoring instruction.

    Args:
        evaluation_steps: The already-numbered evaluation steps.
        test_case_content: The labelled test-case content (the stage output).
        parameters: The list of parameters the metric declares.
        rubric: The formatted rubric bands, or ``None`` when unused.
        score_range: ``(low, high)`` of the whole scale, i.e. ``(0, 10)``.
        decimal_places: Decimal places the judge must use.
        additional_context: Optional extra context prepended to the test case.
    """
    low, high = score_range
    step = 10 ** (-decimal_places)
    # A fractional example is deliberate: an integer example is imitated, which
    # is exactly the behaviour this template exists to prevent. The offset keeps
    # it off the band midpoint so it does not anchor a particular band.
    example = round((low + high) / 2 + 0.3, decimal_places)

    if rubric:
        score_line = (
            f"- `\"score\"`: a number between {low:g} and {high:g}, based on the rubric "
            f"provided.\n"
            f"  Choose the single rubric band that best describes the output, then place the "
            f"score inside that band. A band written as `7-8` means any value from "
            f"{_band_span_text(7, 8, decimal_places)}, so `7.0`, `7.4` and `8.9` are all "
            f"valid for it.\n"
            f"  Use exactly {decimal_places} decimal place(s) so that small differences "
            f"between outputs stay visible. Do not round to a whole number, and do not use "
            f"{low:g} or {high:g} unless the output genuinely sits at an extreme."
        )
        specificity = "the evaluation steps and the rubric"
    else:
        score_line = (
            f"- `\"score\"`: a number between {low:g} and {high:g}, with "
            f"{high:g} indicating strong alignment with the evaluation steps and {low:g} "
            f"indicating no alignment. Use exactly {decimal_places} decimal place(s) rather "
            f"than rounding to a whole number."
        )
        specificity = "the evaluation steps"

    parts = [
        f"You are an evaluator. Given the following evaluation steps"
        f"{' and rubric' if rubric else ''}, assess the response below and return a JSON "
        f"object with two fields:",
        "",
        score_line,
        '- `"reason"`: a brief explanation for why the score was given. This must mention '
        "specific strengths or shortcomings, referencing relevant details from the input. "
        "Do not quote the score itself in the explanation.",
        "",
        "Your explanation should:",
        f"- Be specific and grounded in {specificity}.",
        "- Mention key details from the test case parameters.",
        "- Be concise, clear, and focused on the evaluation logic.",
        "",
        "Only return valid JSON. Do **not** include any extra commentary or text.",
        "",
        "---",
        "",
        "Evaluation Steps:",
        evaluation_steps,
        "",
    ]
    if rubric:
        parts.extend(["Rubric:", rubric, ""])
    parts.extend(["Test Case:", test_case_content, "", "Parameters:", parameters, ""])
    if additional_context:
        parts.extend(["Additional Context:", additional_context, ""])
    parts.extend(
        [
            "---",
            "**Example JSON:**",
            "{",
            '  "reason": "your concise and informative reason here",',
            f'  "score": {example}',
            "}",
            "",
            "JSON:",
        ]
    )
    return "\n".join(parts)


class FractionalScoreGEvalTemplate(GEvalTemplate):
    """G-Eval template that asks for a decimal score inside the chosen band."""

    @staticmethod
    def generate_evaluation_results(**kwargs: Any) -> str:
        """Render the fractional-score evaluation prompt.

        The parameter list is ``**kwargs`` deliberately: DeepEval narrows the
        render context to the parameters an override declares, and accepting the
        full context keeps this override robust to library changes.
        """
        return build_evaluation_prompt(
            evaluation_steps=str(kwargs.get("evaluation_steps", "")),
            test_case_content=str(kwargs.get("test_case_content", "")),
            parameters=str(kwargs.get("parameters", "")),
            rubric=kwargs.get("rubric"),
            score_range=tuple(kwargs.get("score_range", (0, 10))),  # type: ignore[arg-type]
            decimal_places=SCORE_DECIMAL_PLACES,
            additional_context=kwargs.get("_additional_context"),
        )


__all__ = [
    "FractionalScoreGEvalTemplate",
    "build_evaluation_prompt",
]
