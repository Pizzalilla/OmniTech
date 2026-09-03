"""
Agentic loop for the product specification summary.

    Plan     Collect the product, its category and its stored specifications,
             and check the stored data for specifications recorded twice with
             conflicting values.
    Act      Ask the local Ollama model for a shopper-friendly paragraph built
             only from that context.
    Observe  Review the paragraph: the model lists claims the specifications do
             not support and specifications a shopper would expect but that are
             missing, while a numeric check catches figures that appear nowhere
             in the stored data.
    Adapt    Re-prompt once, naming the exact claims to drop, then review again.
             If it still fails the summary is withheld and only the warnings are
             shown, rather than publishing something unsupported.

`run()` is the single entry point used by the Flask layer.
"""

import json
import logging
import re

from backend import ai

logger = logging.getLogger("catalog.agent")

# one first attempt plus a single correction, so a bad model cannot loop forever
MAX_ATTEMPTS = 2

REVIEW_PROMPT = """You are reviewing a product description for factual accuracy.

These are the only facts on record for this product:
{facts}

This is the description to review:
{summary}

Reply with JSON only, in exactly this shape:
{{"unsupported_claims": [], "missing_specifications": []}}

- unsupported_claims: short quotes from the description that state something the
  facts above do not support. Use an empty list if every claim is supported.
- missing_specifications: specifications a shopper would expect for a
  {category_name} but which are not on record. Use an empty list if nothing
  important is missing.

Do not write anything outside the JSON.
"""

CORRECTION_TEMPLATE = """
Your previous answer contained claims that the specifications do not support: {claims}.
Rewrite the paragraph using only the specifications listed above and leave those claims out.
"""


def find_conflicting_specs(specifications: list[dict]) -> list[dict]:
    values_by_name: dict[str, set[str]] = {}
    for spec in specifications:
        name = spec["spec_name"].strip().lower()
        values_by_name.setdefault(name, set()).add(spec["spec_value"].strip())

    return [
        {"spec_name": name, "values": sorted(values)}
        for name, values in sorted(values_by_name.items())
        if len(values) > 1
    ]


def describe_facts(product: dict, specifications: list[dict]) -> str:
    return "\n".join(
        [
            f"- Name: {product['name']}",
            f"- Brand: {product['brand']}",
            f"- Category: {product['category_name']}",
            f"- Price: ${product['price']:.2f}",
            f"- Units in stock: {product['stock']}",
            ai.format_spec_lines(specifications),
        ]
    )


def numbers_in(text: str) -> set[float]:
    # thousands separators would otherwise read as two separate numbers
    return {float(match) for match in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}


def ungrounded_numbers(summary: str, facts: str) -> list[float]:
    return sorted(numbers_in(summary) - numbers_in(facts))


def parse_review(raw: str) -> dict:
    # small models like to wrap json in prose or code fences, so pull out the object
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        return {"unsupported_claims": [], "missing_specifications": []}

    try:
        parsed = json.loads(match.group(0))
    except ValueError:
        return {"unsupported_claims": [], "missing_specifications": []}

    return {
        "unsupported_claims": [str(item) for item in parsed.get("unsupported_claims", [])],
        "missing_specifications": [
            str(item) for item in parsed.get("missing_specifications", [])
        ],
    }


def plan(product: dict, specifications: list[dict]) -> dict:
    context = {
        "product": product,
        "specifications": specifications,
        "facts": describe_facts(product, specifications),
        "prompt": ai.build_summary_prompt(product, specifications),
        "conflicts": find_conflicting_specs(specifications),
    }
    logger.info(
        "PLAN    product=%s specs=%s conflicting_specs=%s",
        product["id"],
        len(specifications),
        len(context["conflicts"]),
    )
    return context


def act(context: dict, correction: str | None = None, attempt: int = 1) -> str:
    prompt = context["prompt"]
    if correction:
        prompt = f"{prompt}{correction}"

    logger.info(
        "ACT     attempt=%s model=%s prompt_chars=%s corrected=%s",
        attempt,
        ai.model_name(),
        len(prompt),
        bool(correction),
    )
    return ai.generate(prompt)


def observe(summary: str, context: dict, attempt: int = 1) -> dict:
    raw = ai.generate(
        REVIEW_PROMPT.format(
            facts=context["facts"],
            summary=summary,
            category_name=context["product"]["category_name"],
        ),
        json_only=True,
    )
    review = parse_review(raw)
    review["ungrounded_numbers"] = ungrounded_numbers(summary, context["facts"])

    logger.info(
        "OBSERVE attempt=%s unsupported_claims=%s missing_specs=%s ungrounded_numbers=%s",
        attempt,
        len(review["unsupported_claims"]),
        len(review["missing_specifications"]),
        len(review["ungrounded_numbers"]),
    )
    return review


def adapt(review: dict, attempt: int) -> str:
    claims = review["unsupported_claims"] + [
        f"the figure {number:g}" for number in review["ungrounded_numbers"]
    ]
    logger.info("ADAPT   attempt=%s re-prompting to drop %s claim(s)", attempt, len(claims))
    return CORRECTION_TEMPLATE.format(claims="; ".join(claims))


def rejected_claims(review: dict) -> list[str]:
    return review["unsupported_claims"] + [
        f"unexplained figure {number:g}" for number in review["ungrounded_numbers"]
    ]


def run(product: dict, specifications: list[dict]) -> dict:
    context = plan(product, specifications)

    attempt = 1
    summary = act(context, attempt=attempt)
    review = observe(summary, context, attempt=attempt)

    # missing specifications describe the stored data, not the paragraph, so the
    # first answer is kept even when a rewrite makes the model forget them
    missing = review["missing_specifications"]

    while rejected_claims(review) and attempt < MAX_ATTEMPTS:
        correction = adapt(review, attempt)
        attempt += 1
        summary = act(context, correction=correction, attempt=attempt)
        review = observe(summary, context, attempt=attempt)

    accepted = not rejected_claims(review)
    logger.info("DONE    accepted=%s attempts=%s", accepted, attempt)

    return {
        "product_id": product["id"],
        "model": ai.model_name(),
        "attempts": attempt,
        "accepted": accepted,
        # a summary that still fails review is withheld rather than shown
        "summary": summary if accepted else None,
        "spec_count": len(specifications),
        "warnings": {
            "conflicting_specs": context["conflicts"],
            "missing_specifications": missing,
            "rejected_claims": rejected_claims(review),
        },
    }
