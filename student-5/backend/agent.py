import os
import re

from datetime import datetime
from llm_client import create_chat_completion
from prompt_loader import load_prompt

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

MAX_RETRIES = 1

def log_agent(stage, message):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [{stage}]", flush=True)
    print(message)
    print("-" * 70, flush=True)

def extract_field(response, field_name):
    pattern = rf"^{re.escape(field_name)}:\s*(.*)$"
    for line in response.splitlines():
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""

def call_agent(system_prompt, user_prompt, max_tokens=300):
    return create_chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=max_tokens,
        temperature=0.2,
        model=OLLAMA_MODEL,
    ).strip()

def plan(ticket):
    context = {
        "system_prompt": load_prompt("system_prompt.txt"),
        "task_prompt": load_prompt("task_prompt.txt"),
        "policy_rules": load_prompt("policy_rules_prompt.txt"),
        "product_category": ticket["product_category"],
        "warranty_claim": ticket["ticket_claim"],
    }
    log_agent("PLAN", f"Ticket {ticket['ticket_id']}: identifying relevant policy rules.")
    return context

def act(context, correction="", attempt=1):
    prompt = f"""
{context["task_prompt"]}

{context["policy_rules"]}

Product Category:
{context["product_category"]}

Warranty Claim:
{context["warranty_claim"]}

Evaluate the claim and return exactly:

DECISION: <Approved or Rejected>
REASONING: <why the decision follows from the claim and policy>
"""
    if correction:
        prompt += f"\n\n{correction}"

    log_agent("ACT", f"Attempt {attempt}: evaluating warranty claim.")

    response = call_agent(
        context["system_prompt"],
        prompt,
        max_tokens=300
    )

    decision = extract_field(response, "DECISION")
    reasoning = extract_field(response, "REASONING")

    log_agent(
        "ACT RESULT",
        f"Decision: {decision}\nReasoning: {reasoning}"
    )

    return {
        "decision": decision,
        "reasoning": reasoning
    }


def observe(evaluation, context, attempt=1):
    prompt = f"""
You are reviewing an AI warranty evaluation.

The AI's WARRANTY DECISION can be either APPROVE or REJECT.
A REJECT decision is completely valid when supported by the policy.

Your job is NOT to decide whether the warranty claim should be approved.
Your job is ONLY to decide whether the AI evaluation is CORRECT.

Original Warranty Claim:
{context["warranty_claim"]}

Product Category:
{context["product_category"]}

Policy Rules:
{context["policy_rules"]}

AI Decision:
{evaluation["decision"]}

AI Reasoning:
{evaluation["reasoning"]}

Review the AI evaluation using these rules:

REVIEW: APPROVED
Use this when the AI's decision and reasoning are supported by
the warranty claim and policy rules.

REVIEW: REJECTED
Use this ONLY when you can identify a specific error in the AI's
decision or reasoning, such as:
- the policy clearly says the opposite
- the AI ignored an important fact in the claim
- the AI applied the wrong policy rule
- the AI invented a fact
- the reasoning does not support the decision

If you cannot identify a specific error, the review MUST be APPROVED.
Do not reject the evaluation merely because the claim itself is rejected.

Return exactly:
REVIEW: APPROVED
FEEDBACK: <why the AI evaluation is correct>

or:
REVIEW: REJECTED
FEEDBACK: <the specific error in the AI evaluation>
"""
    log_agent("OBSERVE", f"Attempt {attempt}: reviewing AI decision.")
    response = call_agent(
        context["system_prompt"],
        prompt,
        max_tokens=300
    )
    review = {
        "status": extract_field(response, "REVIEW"),
        "feedback": extract_field(response, "FEEDBACK")
    }
    log_agent("REVIEW RESULT", f"Review: {review['status']}\nFeedback: {review['feedback']}")
    return review


def adapt(review, attempt):
    log_agent(
        "ADAPT",
        f"Attempt {attempt}: creating correction from reviewer feedback."
    )

    return f"""
The previous evaluation failed review.

Reviewer feedback:
{review["feedback"]}

Re-evaluate the claim and correct the previous decision or reasoning.
"""

def run_agentic_evaluation(ticket):
    context = plan(ticket)
    correction = ""
    for attempt in range(1, MAX_RETRIES + 2):
        evaluation = act(
            context,
            correction=correction,
            attempt=attempt
        )
        if not evaluation["decision"] or not evaluation["reasoning"]:
            review = {
                "status": "REJECTED",
                "feedback": "The AI did not return the required fields."
            }
        else:
            review = observe(
                evaluation,
                context,
                attempt=attempt
            )

        if review["status"].upper().rstrip(".") == "APPROVED":
            log_agent(
                "DONE",
                f"Ticket {ticket['ticket_id']} passed review."
            )
            return {
                "success": True,
                "decision": evaluation["decision"],
                "reasoning": evaluation["reasoning"],
                "review": review,
                "attempts": attempt
            }

        if attempt <= MAX_RETRIES:
            correction = adapt(review, attempt)
    log_agent("FAILED", f"Ticket {ticket['ticket_id']} failed verification.")

    return {
    "success": False,
    "failure_type": "verification_failed",
    "error": (
        f"The AI evaluation was rejected by the review agent "
        f"after {MAX_RETRIES + 1} attempts."
    ),
    "message": (
        "The evaluation completed, but the AI's decision and/or "
        "reasoning did not pass verification."
    ),
    "review": review,
    "attempts": MAX_RETRIES + 1
}