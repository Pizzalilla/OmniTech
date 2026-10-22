import argparse
import json

from shared_agentic_loop import print_report, run_agentic_evaluation

parser = argparse.ArgumentParser()
parser.add_argument(
    "--mode",
    choices=["ai", "mcp", "rag", "multi_agent_workflow_review", "testing_report_review", "cloud_deployment_report_review",],
    required=True,
)
parser.add_argument(
    "--tool",
    help="MCP tool name",
)
parser.add_argument(
    "--args",
    help="JSON arguments for the MCP tool",
)
parser.add_argument(
    "--question",
    help="Question for AI-mode or RAG validation",
)
parser.add_argument(
    "--output",
    help="Also save the final result as JSON to this file (report evidence)",
)
parser.add_argument(
    "--evidence",
    help="Path to a JSON file containing review evidence",
)
parser.add_argument(
    "--student",
    default="group",
    help="Student or group identifier",
)
parser.add_argument(
    "--task",
    help="Additional context for the review",
)
args = parser.parse_args()


# AI-mode (Release 0) or RAG validation
if args.mode in ("ai", "rag"):
    if not args.question:
        parser.error(f"--question is required when --mode {args.mode}")
    ticket = {
        "question": args.question
    }
    result = run_agentic_evaluation(
        ticket,
        validation_mode=args.mode,
    )

# MCP validation
elif args.mode == "mcp":
    if not args.tool:
        parser.error("--tool is required when --mode mcp")
    mcp_arguments = {}
    if args.args:
        try:
            mcp_arguments = json.loads(args.args)
        except json.JSONDecodeError as exc:
            parser.error(f"--args must be valid JSON ({exc})")
    ticket = {
        "request": f"Validate MCP tool: {args.tool}",
    }
    result = run_agentic_evaluation(
        ticket,
        validation_mode="mcp",
        mcp_tool_name=args.tool,
        mcp_arguments=mcp_arguments,
    )

# Release 2 review modes
else:
    if not args.evidence:
        parser.error(
            f"--evidence is required when --mode {args.mode}"
        )

    try:
        with open(args.evidence, "r", encoding="utf-8") as f:
            review_evidence = json.load(f)
    except OSError as exc:
        parser.error(f"Could not read evidence file: {exc}")
    except json.JSONDecodeError as exc:
        parser.error(f"Evidence file must contain valid JSON: {exc}")

    if not isinstance(review_evidence, dict) or not review_evidence:
        parser.error("Evidence file must contain a non-empty JSON object")

    ticket = {
        "student": args.student,
        "evidence": review_evidence,
    }

    if args.task:
        ticket["task"] = args.task

    result = run_agentic_evaluation(
        ticket,
        validation_mode=args.mode,
    )

print_report(result)

if args.output:
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved result to {args.output}")
