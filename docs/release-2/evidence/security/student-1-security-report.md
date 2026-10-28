# Pre-commit security testing report: student-1

- Generated: 2026-10-28 18:30
- Commit: 1ce6e43
- Tools: ruff 0.17.1; detect-secrets 1.5.0; pip-audit 2.10.1

| Scan | Result | Details |
|---|---|---|
| Ruff security rules (S) | PASS | 0 finding(s) |
| detect-secrets | PASS | 0 reviewed in baseline, 0 new |
| pip-audit | PASS | student-1/requirements.txt |

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

First scan (before fixes, commit 1ce6e43) found 2 issues. Both are fixed and the scan above is the re-run:

| Tool | Finding | Fix |
|---|---|---|
| Ruff S608 | `database/db.py:89`: `list_products()` built its SELECT column list with an f-string | The query now starts from `PRODUCT_SELECT`, a fixed string constant, and the filters only add fixed SQL text and `?` placeholders |
| Ruff S608 | `database/db.py:144`: `get_product()` built its SELECT column list with an f-string | Now `PRODUCT_SELECT + " WHERE p.id = ?"`, with the product ID bound as a parameter |

User values were already passed as `?` parameters before the fix, so neither query was exploitable. The change removes the string-built SQL so Ruff no longer flags it. All 110 tests pass after the change.
