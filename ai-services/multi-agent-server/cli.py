"""
Terminal client for the Multi-Agent Server.

    python cli.py run --student student-4 --task "Check this cart" --evidence examples/student4_cart.json
    python cli.py run ... --server http://localhost:6004     (go through the running server)
    python cli.py list [--student student-4]
    python cli.py show wf-1a2b3c4d
    python cli.py decide wf-1a2b3c4d --decision approve

Without --server the workflow runs right here in the terminal (Ollama still
needed). Either way it lands in the same logs/history and logs/audit.jsonl.
"""

import argparse
import json
import sys
from pathlib import Path

import requests

import audit
import workflow as wf


# PRINTING
def heading(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def bullets(items):
    for item in items or []:
        print(f"  - {item}")
    if not items:
        print("  (none)")


def show(item):
    print(f"\nWorkflow {item['id']}  |  {item['student']}  |  status: {item['status']}")
    print(f"Task: {item['task']}")

    if item.get("plan"):
        heading("PLANNER")
        print("Goal:", item["plan"]["goal"])
        print("Steps:")
        bullets(item["plan"]["steps"])
        print("Evidence needed:")
        bullets(item["plan"]["evidence_needed"])

    if item.get("work"):
        heading("WORKER")
        print("Answer:", item["work"]["answer"])
        print("Evidence used:")
        bullets(item["work"]["evidence_used"])
        if item["work"]["issues"]:
            print("Issues:")
            bullets(item["work"]["issues"])

    if item.get("review"):
        heading(f"REVIEWER  ->  {item['review']['verdict'].upper()}")
        print(item["review"]["summary"])
        print("Risks:")
        bullets(item["review"]["risks"])
        print("Recommendations:")
        bullets(item["review"]["recommendations"])
        if item["review"]["checks"]:
            print("Code checks:")
            bullets(item["review"]["checks"])

    if item.get("human"):
        heading(f"HUMAN  ->  {item['human']['decision'].upper()}")
        print("By:", item["human"]["reviewer"])
        if item["human"]["note"]:
            print("Note:", item["human"]["note"])
        print("Final answer:", item.get("final_answer"))

    if item.get("error"):
        print("\nERROR:", item["error"])


# LOCAL OR SERVER: same calls, two ways to do them
def start(args, evidence):
    if args.server:
        resp = requests.post(f"{args.server.rstrip('/')}/workflow/start", timeout=600,
                             json={"student": args.student, "task": args.task, "evidence": evidence})
        return resp.json()
    return wf.start_workflow(args.student, args.task, evidence)


def decide(server, workflow_id, decision, reviewer, note, corrected):
    if server:
        resp = requests.post(f"{server.rstrip('/')}/workflow/{workflow_id}/decision", timeout=30,
                             json={"decision": decision, "reviewer": reviewer,
                                   "note": note, "corrected_answer": corrected})
        data = resp.json()
        if resp.status_code != 200:
            raise ValueError(data.get("error", f"server returned {resp.status_code}"))
        return data
    return wf.apply_decision(workflow_id, decision, reviewer, note, corrected)


# HUMAN STEP: ask in the terminal until we get a valid decision
def ask_human():
    print("\nYour decision: approve / correct / partial / reject")
    while True:
        decision = input("> ").strip().lower()
        if decision in wf.DECISIONS:
            break
        print("Please type approve, correct, partial or reject.")
    corrected = ""
    note = ""
    if decision == "correct":
        corrected = input("Corrected answer: ").strip()
    if decision in ("partial", "reject"):
        note = input("Note (what's accepted / why rejected): ").strip()
    else:
        note = input("Note (optional): ").strip()
    return decision, note, corrected


def load_evidence(args):
    if args.evidence_json:
        return json.loads(args.evidence_json)
    with open(Path(args.evidence), encoding="utf-8") as f:
        return json.load(f)


# COMMANDS
def cmd_run(args):
    evidence = load_evidence(args)
    print(f"Running Planner -> Worker -> Reviewer for {args.student} ...")
    try:
        item = start(args, evidence)
    except ValueError as exc:
        print("Error:", exc)
        return 1
    if "id" not in item:
        print("Error:", item.get("error"))
        return 1
    show(item)
    if item["status"] != "awaiting_human":
        return 1

    if args.decision:
        decision, note, corrected = args.decision, args.note or "", args.corrected or ""
    else:
        decision, note, corrected = ask_human()

    try:
        item = decide(args.server, item["id"], decision, args.reviewer, note, corrected)
    except (ValueError, LookupError, RuntimeError) as exc:
        print("Error:", exc)
        return 1
    show(item)
    return 0


def cmd_decide(args):
    try:
        item = decide(args.server, args.workflow_id, args.decision, args.reviewer,
                      args.note or "", args.corrected or "")
    except (ValueError, LookupError, RuntimeError) as exc:
        print("Error:", exc)
        return 1
    show(item)
    return 0


def cmd_list(args):
    items = audit.list_workflows(args.student)
    if not items:
        print("No workflows yet.")
    for item in items[:args.limit]:
        verdict = (item.get("review") or {}).get("verdict", "-")
        print(f"{item['id']}  {item['created_at']}  {item['student']:<10}  {item['status']:<18}  reviewer={verdict}")
    return 0


def cmd_show(args):
    item = audit.load_workflow(args.workflow_id)
    if item is None:
        print("Workflow not found.")
        return 1
    show(item)
    heading("AUDIT LOG")
    for event in audit.read_events(args.workflow_id):
        print(f"{event['time']}  {event['actor']:<16}  {event['action']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="OmniTech Multi-Agent Server - terminal client")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a new workflow")
    run.add_argument("--student", required=True)
    run.add_argument("--task", required=True)
    group = run.add_mutually_exclusive_group(required=True)
    group.add_argument("--evidence", help="path to a JSON file")
    group.add_argument("--evidence-json", help="evidence as a JSON string")
    run.add_argument("--server", help="e.g. http://localhost:6004 (default: run locally)")
    run.add_argument("--reviewer", default="staff")
    run.add_argument("--decision", choices=list(wf.DECISIONS), help="skip the prompt")
    run.add_argument("--note")
    run.add_argument("--corrected")
    run.set_defaults(func=cmd_run)

    dec = sub.add_parser("decide", help="record a human decision")
    dec.add_argument("workflow_id")
    dec.add_argument("--decision", required=True, choices=list(wf.DECISIONS))
    dec.add_argument("--reviewer", default="staff")
    dec.add_argument("--note")
    dec.add_argument("--corrected")
    dec.add_argument("--server")
    dec.set_defaults(func=cmd_decide)

    lst = sub.add_parser("list", help="workflow history")
    lst.add_argument("--student")
    lst.add_argument("--limit", type=int, default=20)
    lst.set_defaults(func=cmd_list)

    shw = sub.add_parser("show", help="one workflow and its audit log")
    shw.add_argument("workflow_id")
    shw.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
