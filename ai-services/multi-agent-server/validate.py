import argparse
import json

from shared_agentic_loop import print_report, run_agentic_evaluation

parser = argparse.ArgumentParser()
parser.add_argument(
    "--mode",
    choices=["ai", "mcp", "rag"],
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
else:
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

print_report(result)

if args.output:
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved result to {args.output}")
