"""
Build the evidence files for the three Release 2 agentic-loop review modes
from the real reports in the repository, so nothing is typed in by hand.

    python build_review_evidence.py            # writes review_evidence/*.json

Sources (anything missing is listed under "missing_evidence" instead of being guessed):
  multi_agent_workflow.json  docs/release-2/evidence/multi-agent/*.json (completed workflows)
  testing_report.json        docs/release-2/evidence/security/*-security-report.md,
                             each student's endpoint test file and latest CI run on main
  cloud_deployment.json      docs/release-2/evidence/cloud/ (deployment.json,
                             cloud-smoke-results.json, cloud-security-results.json)
                             and the AI-off settings in scripts/deploy/azure/config.sh

The agents read at most MAX_EVIDENCE_CHARS (6000) of evidence, so each file is a
compact summary that points back to the full report it came from.
"""

import ast
import json
import re
import ssl
import urllib.request
from pathlib import Path

import workflow as wf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVIDENCE = ROOT / "docs" / "release-2" / "evidence"
OUT = HERE / "review_evidence"
REPO = "Pizzalilla/OmniTech"
STUDENTS = ["student-1", "student-2", "student-3", "student-4", "student-5"]
# the file each student's workflow runs as its two-endpoint post-commit tests
ENDPOINT_TEST_FILES = ["tests/test_endpoints.py", "tests/test_post_commit_endpoints.py",
                       "tests/test_api.py", "tests/test_app.py", "tests/test_tickets.py"]
LIMIT = 5500

# python.org builds on macOS ship without root certificates; use certifi's bundle when present.
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


def short(text, n=240):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 3] + "..."


def write(name, data):
    OUT.mkdir(exist_ok=True)
    text = json.dumps(data, indent=2)
    path = OUT / name
    path.write_text(text + "\n")
    flag = "" if len(text) <= LIMIT else f"  WARNING: {len(text)} chars, agents read only the first 6000"
    print(f"{path.relative_to(ROOT)}: {len(text)} chars{flag}")


# ── Multi-Agent workflow evidence ───────────────────────────────────────────

def summarise_workflow(path):
    w = json.loads(path.read_text(encoding="utf-8-sig"))
    plan, work, review, human = (w.get(k) or {} for k in ("plan", "work", "review", "human"))
    return {
        "source": str(path.relative_to(ROOT)),
        "workflow_id": w.get("id"),
        "student": w.get("student"),
        "task": short(w.get("task"), 200),
        "evidence_supplied": list((w.get("evidence") or {}).keys()),
        "planner": {"goal": short(plan.get("goal"), 150), "steps": len(plan.get("steps") or [])},
        "worker": {"answer": short(work.get("answer"), 260), "evidence_used": work.get("evidence_used"),
                   "issues": work.get("issues")},
        "reviewer": {"verdict": review.get("verdict"), "summary": short(review.get("summary"), 200),
                     "risks": [short(r, 120) for r in review.get("risks") or []][:3]},
        "human_review": {"decision": human.get("decision"), "reviewer": human.get("reviewer"),
                         "note": short(human.get("note"), 150),
                         "agreed_with_reviewer": human.get("agreed_with_reviewer")},
        "final_status": w.get("status"),
        "audit_trail": [e.get("action") for e in w.get("events") or []],
    }


def count_tests(path):
    tree = ast.parse(path.read_text())
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))


def multi_agent_evidence():
    records = sorted((EVIDENCE / "multi-agent").glob("*.json"))
    covered = {json.loads(p.read_text(encoding="utf-8-sig")).get("student") for p in records}
    return {
        "implementation": {
            "server": "ai-services/multi-agent-server/server.py, port 6004, non-containerised",
            "agents": "Planner -> Worker -> Reviewer (agents.py), then a human decision (workflow.py)",
            "human_decisions": list(wf.DECISIONS),
            "decision_rules": "correct needs a corrected answer; partial and reject need a note",
            "endpoints": ["POST /workflow/start", "POST /workflow/<id>/decision", "GET /workflow/<id>",
                          "GET /workflows", "GET /audit"],
            "terminal_access": "cli.py run / decide / list / show use the same workflow and logs",
            "audit": "logs/history/<id>.json per workflow, logs/audit.jsonl one line per event",
            "evidence_flow": ("the feature backend sends task + evidence; the Planner lists the evidence it "
                              "needs; the Worker answers only from that evidence and names what it used; the "
                              "Reviewer checks the answer against the plan and evidence; the human decides"),
            "error_handling": [
                "missing student, task or evidence -> HTTP 400 before any agent runs",
                "Ollama unreachable, non-JSON reply or empty plan -> workflow status 'failed', HTTP 503, "
                "error saved in the audit log; feature UIs show a clear message",
                "decision on an unknown workflow -> 404; on one already decided -> 409; invalid decision "
                "or missing note / corrected answer -> 400",
                "evidence over 6000 characters is cut short so prompts stay within the model's context",
            ],
            "automated_tests": count_tests(HERE / "tests" / "test_multi_agent.py"),
        },
        "completed_workflows": [summarise_workflow(p) for p in records],
        "missing_evidence": [f"no completed workflow record from {s}" for s in STUDENTS if s not in covered],
    }


# ── Testing evidence ────────────────────────────────────────────────────────

def parse_security_report(path):
    text = path.read_text()
    rows = dict(re.findall(r"^\| (Ruff security rules \(S\)|detect-secrets|pip-audit) \| (\w+) \|", text, re.M))
    commit = re.search(r"- Commit: (\S+)", text)
    resolution = text.split("## Resolution of findings", 1)[-1]
    fixes = re.findall(r"^\| (Ruff \w+|pip-audit) \| ([^|]+)\|", resolution, re.M)
    return {
        "source": str(path.relative_to(ROOT)),
        "commit": commit.group(1) if commit else None,
        "ruff_security": rows.get("Ruff security rules (S)", "unknown"),
        # key avoids the word "secret" so detect-secrets doesn't flag this result as a credential
        "credential_scan": rows.get("detect-secrets", "unknown"),
        "pip_audit": rows.get("pip-audit", "unknown"),
        "findings_fixed": [short(f"{tool}: {what}", 70) for tool, what in fixes][:3],
    }


def latest_ci_run(student):
    url = (f"https://api.github.com/repos/{REPO}/actions/workflows/{student}.yml/runs"
           "?branch=main&per_page=1")
    try:
        with urllib.request.urlopen(url, timeout=15, context=SSL_CONTEXT) as resp:  # noqa: S310 - fixed https URL
            runs = json.load(resp)["workflow_runs"]
    except (OSError, ValueError, KeyError) as exc:
        return {"error": f"could not read GitHub Actions: {exc}"}
    if not runs:
        return {"error": "no runs on main"}
    r = runs[0]
    return {"conclusion": r["conclusion"], "date": r["created_at"][:10], "url": r["html_url"]}


def endpoint_tests(student):
    for rel in ENDPOINT_TEST_FILES:
        path = ROOT / student / rel
        if not path.exists():
            continue
        names = [n.name for n in ast.walk(ast.parse(path.read_text()))
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        if names:  # skip helper-only files such as a shared fixture module
            return {"file": f"{student}/{rel}", "count": len(names), "examples": names[:3]}
    return None


def testing_evidence():
    reports = {p.name.replace("-security-report.md", ""): parse_security_report(p)
               for p in sorted((EVIDENCE / "security").glob("*-security-report.md"))}
    students, missing = {}, []
    for s in STUDENTS:
        tests = endpoint_tests(s)
        students[s] = {"pre_commit_security": reports.get(s), "post_commit_endpoint_tests": tests,
                       "latest_ci_run_on_main": latest_ci_run(s)}
        if s not in reports:
            missing.append(f"{s}: no security report in docs/release-2/evidence/security/")
        if not tests:
            missing.append(f"{s}: no endpoint test file found")
    return {
        "pre_commit_tools": "Ruff security rules (S), detect-secrets, pip-audit, run by .pre-commit-config.yaml on every commit",
        "students": students,
        "shared_services": {k: v for k, v in reports.items() if k not in STUDENTS},
        "missing_evidence": missing,
    }


# ── Cloud deployment evidence ───────────────────────────────────────────────

def ai_off_settings():
    text = (ROOT / "scripts" / "deploy" / "azure" / "config.sh").read_text()
    block = text.split("AI_DISABLED_ENV=(", 1)[1].split(")", 1)[0]
    return re.findall(r'"([A-Z_]+=[^"]+)"', block)


def cloud_evidence():
    cloud = EVIDENCE / "cloud"
    data, missing = {}, []
    dep = cloud / "deployment.json"
    if dep.exists():
        d = json.loads(dep.read_text())
        data["deployment"] = {"platform": "Azure Container Apps", "deployed_at": d.get("deployed_at"),
                              "commit": d.get("commit"), "region": d.get("region"),
                              "resource_group": d.get("resource_group"), "services": d.get("services")}
    else:
        missing.append("deployment.json")
    smoke = cloud / "cloud-smoke-results.json"
    if smoke.exists():
        s = json.loads(smoke.read_text())
        data["smoke_test"] = {
            "checked_at": s.get("checked_at"), "passed": s.get("passed"), "total": s.get("total"),
            "checks": [f"{r['service']}: {r['check']} -> {r['status']} ({'PASS' if r['passed'] else 'FAIL'})"
                       for r in s.get("results", [])],
        }
    else:
        missing.append("cloud-smoke-results.json")
    sec = cloud / "cloud-security-results.json"
    if sec.exists():
        c = json.loads(sec.read_text())
        by_area = {}
        for r in c.get("results", []):
            a = by_area.setdefault(r["area"], {"passed": 0, "total": 0, "controls": set()})
            a["total"] += 1
            a["passed"] += r["passed"]
            a["controls"].add(r["control"])
        data["security_validation"] = {
            "checked_at": c.get("checked_at"), "passed": c.get("passed"), "total": c.get("total"),
            "by_area": {k: {"passed": v["passed"], "total": v["total"], "controls": sorted(v["controls"])}
                        for k, v in by_area.items()},
            "failed": [f"{r['target']}: {r['control']}" for r in c.get("results", []) if not r["passed"]],
        }
    else:
        missing.append("cloud-security-results.json")
    data["ai_services_disabled_by_default"] = {
        "settings_applied_to_every_app": ai_off_settings(),
        "not_deployed": ["Ollama (AI-Mode)", "MCP Server", "RAG Server", "Multi-Agent Server"],
    }
    data["missing_evidence"] = missing
    data["note"] = ("Copy the latest cloud-deployment-evidence artifact into docs/release-2/evidence/cloud/ "
                    "before building, so this reflects the final deployment.")
    return data


if __name__ == "__main__":
    write("multi_agent_workflow.json", multi_agent_evidence())
    write("testing_report.json", testing_evidence())
    write("cloud_deployment.json", cloud_evidence())
