import argparse

from shared_agentic_loop import run_agentic_evaluation


parser = argparse.ArgumentParser()

parser.add_argument(
    "--mode",
    choices=["mcp", "rag"],
    required=True,
)

parser.add_argument(
    "--tool",
    help="MCP tool name, required for MCP mode",
)

parser.add_argument(
    "--args",
    help="JSON arguments for the MCP tool",
)

args = parser.parse_args()


ticket = {
    "product": "Hard Drive",
    "description": "The hard drive was physically damaged by the customer.",
}


mcp_arguments = None

if args.args:
    import json
    mcp_arguments = json.loads(args.args)


result = run_agentic_evaluation(
    ticket,
    validation_mode=args.mode,
    mcp_tool_name=args.tool,
    mcp_arguments=mcp_arguments,
)

print("\nFINAL RESULT:")
print(result)