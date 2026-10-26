# Pre-commit security testing report: student-3

- Generated: 2026-10-20 00:22
- Commit: 664cef0
- Tools: ruff 0.17.1; detect-secrets 1.5.0; pip-audit 2.10.1

| Scan | Result | Details |
|---|---|---|
| Ruff security rules (S) | PASS | 0 finding(s) |
| detect-secrets | PASS | 0 reviewed in baseline, 0 new |
| pip-audit | PASS | student-3/requirements.txt |

## Ruff security rules

```
All checks passed!
```

## detect-secrets

```
0 potential secret(s) in this project are already reviewed in .secrets.baseline.
No new secrets found.
```

## pip-audit

```
No known vulnerabilities found
```

## Resolution of findings

First scan (before fixes, `main` at 664cef0) found 4 issues. All are fixed and the scan above is the re-run:

| Tool | Finding | Fix |
|---|---|---|
| Ruff S201 | `backend/main.py`: `app.run(debug=True)` exposes the Werkzeug interactive debugger, which can run code | Debug is now off unless `FLASK_DEBUG=1` is set; the cloud deployment sets `FLASK_DEBUG=0` |
| Ruff S104 | `backend/main.py`: binds to `0.0.0.0` | Kept on purpose: inside the container this is required so Docker / Azure Container Apps can route traffic in. Documented with `# noqa: S104` and a reason |
| pip-audit | requests 2.32.5, PYSEC-2026-2275 | `requirements.txt` now pins `requests==2.33.*` |
| pip-audit | pytest 8.3.5, PYSEC-2026-1845 | `requirements.txt` now pins `pytest==9.0.*` |

All 77 tests pass with the upgraded packages.
