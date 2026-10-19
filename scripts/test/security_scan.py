"""Run the Release 2 security scans for one project and write a Markdown report.

Usage (from the repo root):
    python scripts/test/security_scan.py student-3
    python scripts/test/security_scan.py ai-services/rag-server
    python scripts/test/security_scan.py all

Reports go to docs/release-2/evidence/security/<project>-security-report.md.
Runs the same tools as the pre-commit hooks: Ruff security rules (ruff.toml),
detect-secrets (against .secrets.baseline) and pip-audit.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "release-2" / "evidence" / "security"
PY = sys.executable
BINARY = re.compile(r"\.(png|jpe?g|pdf|db|ttf|ico)$", re.I)


def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def tracked(target):
    _, out = run(["git", "ls-files", target])
    return [f for f in out.splitlines() if f and not BINARY.search(f)]


def version(module):
    _, out = run([PY, "-m", module, "--version"])
    return out.splitlines()[0] if out else "unknown"


def ruff_scan(target):
    code, out = run([PY, "-m", "ruff", "check", target, "--no-fix", "--output-format", "concise"])
    findings = [ln for ln in out.splitlines() if re.search(r":\d+:\d+: S\d+", ln)]
    return code, out or "No findings.", findings


def secrets_scan(target):
    files = tracked(target)
    if not files:
        return 0, "No files to scan.", 0
    code, out = run([PY, "-m", "detect_secrets.pre_commit_hook", "--baseline", ".secrets.baseline", *files])
    baseline = json.loads((ROOT / ".secrets.baseline").read_text())["results"]
    known = sum(len(v) for k, v in baseline.items() if k.startswith(target.rstrip("/") + "/"))
    summary = (f"{known} potential secret(s) in this project are already reviewed in .secrets.baseline.\n"
               + ("No new secrets found." if code == 0 else "NEW potential secrets found:\n" + out))
    return code, summary, known


def pip_audit_scan(target):
    reqs = [f for f in tracked(target) if Path(f).name == "requirements.txt"]
    if not reqs:
        return 0, "No requirements.txt in this project.", reqs
    cmd = [PY, "-m", "pip_audit", "--progress-spinner", "off"]
    for r in reqs:
        cmd += ["-r", r]
    code, out = run(cmd)
    return code, out, reqs


def report(target):
    name = target.rstrip("/").replace("/", "-")
    _, commit = run(["git", "rev-parse", "--short", "HEAD"])
    r_code, r_out, r_findings = ruff_scan(target)
    s_code, s_out, s_known = secrets_scan(target)
    a_code, a_out, a_reqs = pip_audit_scan(target)

    def status(code):
        return "PASS" if code == 0 else "FINDINGS"

    lines = [
        f"# Pre-commit security testing report: {target}",
        "",
        f"- Generated: {datetime.now():%Y-%m-%d %H:%M}",
        f"- Commit: {commit}",
        f"- Tools: {version('ruff')}; detect-secrets {version('detect_secrets')}; {version('pip_audit')}",
        "",
        "| Scan | Result | Details |",
        "|---|---|---|",
        f"| Ruff security rules (S) | {status(r_code)} | {len(r_findings)} finding(s) |",
        f"| detect-secrets | {status(s_code)} | {s_known} reviewed in baseline, "
        f"{'0 new' if s_code == 0 else 'new findings'} |",
        f"| pip-audit | {status(a_code)} | {', '.join(a_reqs) or 'no requirements.txt'} |",
        "",
        "## Ruff security rules", "", "```", r_out, "```", "",
        "## detect-secrets", "", "```", s_out, "```", "",
        "## pip-audit", "", "```", a_out, "```", "",
        "## Resolution of findings", "",
        "Each finding is fixed or explained here:", "",
    ]
    lines += [f"- `{f}`: action: " for f in r_findings] or ["- No Ruff findings."]
    if a_code:
        lines.append("- pip-audit vulnerabilities above: action: ")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}-security-report.md"
    path.write_text("\n".join(lines) + "\n")
    print(f"{target}: ruff {status(r_code)} ({len(r_findings)}), "
          f"secrets {status(s_code)}, pip-audit {status(a_code)} -> {path.relative_to(ROOT)}")
    return max(r_code, s_code, a_code)


def projects():
    tops = sorted(p.name for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("student-"))
    ais = sorted(f"ai-services/{p.name}" for p in (ROOT / "ai-services").iterdir() if p.is_dir())
    return tops + ais


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    targets = projects() if sys.argv[1] == "all" else [sys.argv[1]]
    sys.exit(max(report(t) for t in targets))
