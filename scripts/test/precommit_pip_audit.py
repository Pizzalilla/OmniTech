"""pre-commit hook: pip-audit the requirements of every project the commit touches.

A project is a top-level student-N/ folder or an ai-services/<name>/ folder.
"""

import subprocess
import sys
from pathlib import Path


def project_root(path):
    parts = Path(path).parts
    if parts[0].startswith("student-"):
        return Path(parts[0])
    if parts[0] == "ai-services" and len(parts) > 1:
        return Path(parts[0], parts[1])
    return None


def requirements_in(root):
    tracked = subprocess.run(["git", "ls-files", str(root)], capture_output=True, text=True, check=True)
    return sorted(f for f in tracked.stdout.split() if Path(f).name == "requirements.txt")


def main(changed):
    roots = sorted({r for r in map(project_root, changed) if r})
    status = 0
    for root in roots:
        reqs = requirements_in(root)
        if not reqs:
            continue
        print(f"pip-audit: {root} ({', '.join(reqs)})")
        cmd = [sys.executable, "-m", "pip_audit", "--progress-spinner", "off"]
        for req in reqs:
            cmd += ["-r", req]
        status |= subprocess.run(cmd).returncode
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
