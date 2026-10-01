import os

import requests

DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 60


class AIUnavailable(Exception):
    """Ollama could not be reached, or answered with something unusable."""


SUMMARY_PROMPT = """You are a retail assistant for OmniTech, an online appliance store.

Write one paragraph of 50 to 80 words that helps a shopper decide whether this product suits them.

Rules:
- Use only the product details and specifications listed below.
- Never invent a specification, measurement, price, or claim.
- Mention at most three specifications, chosen for how much a shopper would care.
- Write plain prose. No bullet points, headings, or markdown.

Product: {name}
Brand: {brand}
Category: {category_name}
Price: ${price:.2f}
Units in stock: {stock}
Description: {description}

Specifications:
{spec_lines}
"""


def ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def model_name() -> str:
    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)


def request_timeout() -> int:
    try:
        return int(os.getenv("OLLAMA_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        return DEFAULT_TIMEOUT


def generate(prompt: str, json_only: bool = False) -> str:
    payload = {
        "model": model_name(),
        "prompt": prompt,
        "stream": False,
        # a low temperature keeps the model close to the supplied specs
        "options": {"temperature": 0.2},
    }
    if json_only:
        # ollama constrains the decoder to valid json, which small models
        # otherwise wrap in prose or code fences
        payload["format"] = "json"

    try:
        response = requests.post(
            f"{ollama_host()}/api/generate",
            json=payload,
            timeout=request_timeout(),
        )
        response.raise_for_status()
        text = response.json().get("response", "")
    except requests.RequestException as exc:
        raise AIUnavailable(f"could not reach ollama at {ollama_host()}: {exc}") from exc
    except ValueError as exc:
        raise AIUnavailable("ollama returned a malformed response") from exc

    text = text.strip()
    if not text:
        raise AIUnavailable("ollama returned an empty response")
    return text


def format_spec_lines(specifications: list[dict]) -> str:
    if not specifications:
        return "- none recorded"
    return "\n".join(
        f"- {spec['spec_name']}: {spec['spec_value']}" for spec in specifications
    )


def build_summary_prompt(product: dict, specifications: list[dict]) -> str:
    return SUMMARY_PROMPT.format(
        name=product["name"],
        brand=product["brand"],
        category_name=product["category_name"],
        price=product["price"],
        stock=product["stock"],
        description=product["description"] or "not provided",
        spec_lines=format_spec_lines(specifications),
    )


def summarise_product(product: dict, specifications: list[dict]) -> dict:
    return {
        "product_id": product["id"],
        "model": model_name(),
        "summary": generate(build_summary_prompt(product, specifications)),
    }
