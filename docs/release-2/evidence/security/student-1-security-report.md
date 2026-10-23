# Pre-commit security testing report: student-1

- Generated: 2026-10-23 07:54
- Commit: 2a09a87
- Tools: ruff 0.17.1; detect-secrets 1.5.0; pip-audit 2.10.1

| Scan | Result | Details |
|---|---|---|
| Ruff security rules (S) | FINDINGS | 2 finding(s) |
| detect-secrets | PASS | 0 reviewed in baseline, 0 new |
| pip-audit | PASS | student-1/requirements.txt |

## Ruff security rules

```
student-1\database\db.py:89:13: S608 Possible SQL injection vector through string-based query construction
student-1\database\db.py:144:13: S608 Possible SQL injection vector through string-based query construction
Found 2 errors.
```

## detect-secrets

```
0 potential secret(s) in this project are already reviewed in .secrets.baseline.
No new secrets found.
```

## pip-audit

```
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
WARNING:cachecontrol.controller:Cache entry deserialization failed, entry ignored
No known vulnerabilities found
```

## Resolution of findings

Each finding is fixed or explained here:

- `student-1\database\db.py:89:13: S608 Possible SQL injection vector through string-based query construction`: action: 
- `student-1\database\db.py:144:13: S608 Possible SQL injection vector through string-based query construction`: action: 
