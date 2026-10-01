"""
Terminal validation for the shared MCP server (evidence for the report).

    python validate.py                   # checks http://localhost:6003
    python validate.py --only student4   # only one student's tools

Checks the handshake, that every tool has a name / description / input
schema, calls every tool with its example, and checks the boundaries
(unknown tool, missing argument, wrong type are all rejected).
"""

import argparse
import json
import os
import sys

import requests

from client import McpClient, McpError

MCP_HOST = os.getenv("MCP_HOST", "http://localhost:6003")
results = {"PASS": 0, "FAIL": 0, "WARN": 0}


def report(status, text):
    results[status] += 1
    print(f"  [{status}] {text}")


def short(data, limit=160):
    text = json.dumps(data)
    return text if len(text) <= limit else text[:limit] + "..."


def expect_rejected(mcp, label, name, arguments):
    try:
        mcp.call_tool(name, arguments)
        report("FAIL", f"{label}: was NOT rejected")
    except McpError as exc:
        report("PASS", f"{label}: rejected ({exc})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="only check tools owned by this file, e.g. student4")
    args = parser.parse_args()

    mcp = McpClient(MCP_HOST)
    print(f"MCP server: {MCP_HOST}")

    # 1. HEALTH + HANDSHAKE
    print("\n1. Handshake")
    try:
        health = requests.get(f"{MCP_HOST}/health", timeout=5).json()
    except requests.RequestException:
        print("  [FAIL] server not reachable - start it with: python server.py")
        sys.exit(1)
    report("PASS", f"health: {health['status']}, {len(health['tools'])} tool(s)")
    info = mcp.initialize("validate.py")
    report("PASS", f"initialize: {info['serverInfo']['name']} v{info['serverInfo']['version']}, "
                   f"protocol {info['protocolVersion']}")

    # 2. TOOL LIST
    print("\n2. Tool list")
    tools = mcp.list_tools()
    owners = health.get("owners", {})
    if args.only:
        tools = [t for t in tools if owners.get(t["name"]) == args.only]
    for t in tools:
        ok = t.get("name") and t.get("description") and t.get("inputSchema", {}).get("type") == "object"
        report("PASS" if ok else "FAIL",
               f"{t['name']}({', '.join(t['inputSchema']['properties'])}) - {t['description']}")

    # 3. CALL EVERY TOOL WITH ITS EXAMPLE
    print("\n3. Tool calls")
    examples = health.get("examples", {})
    for t in tools:
        example = examples.get(t["name"], {})
        try:
            res = mcp.call_tool(t["name"], example)
        except McpError as exc:
            report("FAIL", f"{t['name']}{short(example)} -> {exc}")
            continue
        if res["isError"]:
            # the tool worked but the student's service answered with an error / is not running
            report("WARN", f"{t['name']}{short(example)} -> tool error: {res['content'][0]['text']}")
        elif isinstance(res.get("structuredContent"), dict):
            report("PASS", f"{t['name']}{short(example)} -> {short(res['structuredContent'])}")
        else:
            report("FAIL", f"{t['name']} returned no structured result")

    # 4. BOUNDARIES
    print("\n4. Boundaries")
    expect_rejected(mcp, "unknown tool", "delete_everything", {})
    for t in tools:
        schema = t["inputSchema"]
        if schema["required"]:
            expect_rejected(mcp, f"{t['name']} with no arguments", t["name"], {})
            first = schema["required"][0]
            expect_rejected(mcp, f"{t['name']} with wrong type for '{first}'", t["name"], {first: "not-valid"})
        expect_rejected(mcp, f"{t['name']} with an extra argument",
                        t["name"], {**examples.get(t["name"], {}), "drop_table": True})

    print(f"\nResult: {results['PASS']} passed, {results['WARN']} warning(s), {results['FAIL']} failed")
    if results["WARN"]:
        print("Warnings mean a tool worked but its student service is not running or returned an error.")
    sys.exit(1 if results["FAIL"] else 0)


if __name__ == "__main__":
    main()
