# Pre-commit security testing (Release 2)

Every commit runs three security scans locally before it is created:

| Scan | Tool | What it checks |
|---|---|---|
| Code security | Ruff security rules (`S`, from flake8-bandit) | e.g. `debug=True`, SQL built from strings, hard-coded passwords |
| Secrets | detect-secrets | API keys, tokens and passwords in any committed file |
| Dependencies | pip-audit | known vulnerabilities in the `requirements.txt` of each project you changed |

Configuration: `.pre-commit-config.yaml`, `ruff.toml` and `.secrets.baseline` (repo root).

## Setup (once per laptop)

```bash
pip install -r scripts/test/requirements-security.txt
pre-commit install
```

From then on the scans run on every `git commit`. A failing scan blocks the commit
until you fix it. GitHub Desktop should run the same hook; if a commit from Desktop
skips the scans, commit from the terminal instead.

## Your security report (for the technical report)

```bash
python scripts/test/security_scan.py student-3
```

It writes `docs/release-2/evidence/security/student-3-security-report.md` with each
scan's result. Fix what you can, then fill in **Resolution of findings**: one line per
finding saying what you changed, or why it is accepted (for example binding to
`0.0.0.0` is needed so Docker can reach the app). Re-run the script after fixing and
commit the report.

## Findings already in the repo (scan of 19 Oct)

- **Everyone:** `requests` 2.32.5 and `pytest` 8.3.5 have known vulnerabilities. Bump to
  `requests>=2.33.0` and `pytest>=9.0.3` in your `requirements.txt`.
- **Student 1:** `python-dotenv` 1.0.1 (bump to 1.2.2); two `S608` SQL-string warnings in `database/db.py`.
- **Student 5:** `flask-cors` 4.0.1 (bump to 6.0.0).
- **Most students:** `S201` `debug=True` in `app.run` (read it from an environment variable
  instead) and `S104` binding to `0.0.0.0` (needed in containers: keep it and add
  `# noqa: S104` with a one-line reason above it).

## Notes

- To check everything without committing: `pre-commit run --all-files`.
- A false positive from detect-secrets: add `# pragma: allowlist secret` on that line.
- Never use `git commit --no-verify` to skip the scans; the brief requires them to run on commit.
