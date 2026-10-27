# Pre-commit security testing report: student-5

- Generated: 2026-10-27 15:16
- Commit: da360a0
- Tools: ruff 0.17.3; detect-secrets 1.5.0; pip-audit 2.10.1

| Scan | Result | Details |
|---|---|---|
| Ruff security rules (S) | FINDINGS | 3 finding(s) |
| detect-secrets | PASS | 0 reviewed in baseline, 0 new |
| pip-audit | FINDINGS | student-5/backend/requirements.txt, student-5/requirements.txt |

## Ruff security rules

```
student-5/backend/main.py:701:18: S104 Possible binding to all interfaces
student-5/backend/main.py:701:40: S201 Use of `debug=True` in Flask app detected
student-5/database/app.py:57:42: S201 Use of `debug=True` in Flask app detected
Found 3 errors.
```

## detect-secrets

```
0 potential secret(s) in this project are already reviewed in .secrets.baseline.
No new secrets found.
```

## pip-audit

```
Name       Version ID              Fix Versions
---------- ------- --------------- ------------
flask-cors 4.0.1   PYSEC-2024-71   4.0.2
flask-cors 4.0.1   PYSEC-2024-71   4.0.2
flask-cors 4.0.1   PYSEC-2026-1385 6.0.0
flask-cors 4.0.1   PYSEC-2026-1383 6.0.0
flask-cors 4.0.1   PYSEC-2026-1384 6.0.0
flask-cors 4.0.1   PYSEC-2026-1383 6.0.0
flask-cors 4.0.1   PYSEC-2026-1384 6.0.0
flask-cors 4.0.1   PYSEC-2026-1385 6.0.0
requests   2.32.5  PYSEC-2026-2275 2.33.0
requests   2.32.5  PYSEC-2026-2275 2.33.0
pytest     8.3.5   PYSEC-2026-1845 9.0.3
pytest     8.3.5   PYSEC-2026-1845 9.0.3
Found 12 known vulnerabilities in 3 packages
```

## Resolution of findings

Each finding is fixed or explained here:

- `student-5/backend/main.py:701:18: S104 Possible binding to all interfaces`: action: 
- `student-5/backend/main.py:701:40: S201 Use of `debug=True` in Flask app detected`: action: 
- `student-5/database/app.py:57:42: S201 Use of `debug=True` in Flask app detected`: action: 
- pip-audit vulnerabilities above: action: 
