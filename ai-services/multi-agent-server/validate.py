import argparse
import json

from shared_agentic_loop import run_agentic_evaluation

parser = argparse.ArgumentParser()
parser.add_argument(
    "--mode",
    choices=["mcp", "rag"],
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
    help="Question for RAG validation",
)
args = parser.parse_args()


# RAG validation
if args.mode == "rag":
    if not args.question:
        parser.error("--question is required when --mode rag")
    ticket = {
        "question": args.question
    }
    result = run_agentic_evaluation(
        ticket,
        validation_mode="rag",
    )

# MCP validation
else:
    if not args.tool:
        parser.error("--tool is required when --mode mcp")
    mcp_arguments = {}
    if args.args:
        mcp_arguments = json.loads(args.args)
    ticket = {
        "request": f"Validate MCP tool: {args.tool}",
    }
    result = run_agentic_evaluation(
        ticket,
        validation_mode="mcp",
        mcp_tool_name=args.tool,
        mcp_arguments=mcp_arguments,
    )

print("\nFINAL RESULT:")
print(result)