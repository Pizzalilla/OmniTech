# Pre-commit security testing report: ai-services/rag-server

- Generated: 2026-10-20 00:22
- Commit: 664cef0
- Tools: ruff 0.17.1; detect-secrets 1.5.0; pip-audit 2.10.1

| Scan | Result | Details |
|---|---|---|
| Ruff security rules (S) | PASS | 0 finding(s) |
| detect-secrets | PASS | 0 reviewed in baseline, 0 new |
| pip-audit | PASS | ai-services/rag-server/requirements.txt |

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

First scan found 3 issues, all fixed; the scan above is the re-run:

- Ruff S104, `server.py`: binds to `0.0.0.0` so student containers can reach the server through `host.docker.internal`. Kept on purpose and documented with `# noqa: S104`.
- pip-audit: requests 2.32.5 (PYSEC-2026-2275) -> `requests==2.33.*`.
- pip-audit: pytest 8.3.5 (PYSEC-2026-1845) -> `pytest==9.0.*`. All 13 RAG server tests pass after the upgrade.
