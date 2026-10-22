"""Validate the cloud security controls and write the cloud security report.

Usage (after deploy.sh, logged in with `az login`):
    SMOKE_AUTH=omnitech:<password> python scripts/deploy/azure/security_check.py

Two kinds of evidence, both written to docs/release-2/evidence/cloud/:
  * Endpoint security - live requests against every deployed app (HTTPS redirect,
    TLS version, login required, security headers, hidden files, upload limit,
    rate limiting).
  * Data security - the Azure configuration read back with `az`: where the password
    lives, how apps pull images, which roles each identity holds.
SMOKE_AUTH is optional; without it the "correct login" check is skipped.
"""

import base64
import http.client
import json
import os
import ssl
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smoke_test import SSL_CONTEXT  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs" / "release-2" / "evidence" / "cloud"
AUTH = os.getenv("SMOKE_AUTH", "")
REQUIRED_HEADERS = ["Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options",
                    "Referrer-Policy", "Permissions-Policy"]

results = []


def record(area, control, target, passed, detail):
    results.append({"area": area, "control": control, "target": target,
                    "passed": bool(passed), "detail": detail})
    print(f"{'PASS' if passed else 'FAIL'}  {area:8} {target:10} {control}: {detail}", flush=True)


# ── HTTP helpers (no redirect following, so redirects can be checked) ───────

def fetch(url, method="GET", headers=None, body=None, timeout=60):
    u = urlparse(url)
    if u.scheme == "https":
        conn = http.client.HTTPSConnection(u.netloc, timeout=timeout, context=SSL_CONTEXT)
    elif u.scheme == "http":
        conn = http.client.HTTPConnection(u.netloc, timeout=timeout)  # noqa: S309 - checks the HTTP->HTTPS redirect
    else:
        raise ValueError(f"refusing non-HTTP URL: {url}")
    try:
        conn.request(method, u.path or "/", body=body, headers=headers or {})
        resp = conn.getresponse()
        resp.read()
        tls = conn.sock.version() if u.scheme == "https" and conn.sock else None
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, tls
    finally:
        conn.close()


def basic(user_pass):
    return {"Authorization": "Basic " + base64.b64encode(user_pass.encode()).decode()}


def wake(url, wait=150):
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            fetch(url, timeout=30)
            return True
        except OSError:
            time.sleep(5)
    return False


# ── Endpoint security ───────────────────────────────────────────────────────

def endpoint_checks(name, base):
    if not wake(base + "/"):
        record("endpoint", "Service reachable", name, False, "did not start")
        return
    status, headers, _ = fetch(base.replace("https://", "http://", 1) + "/")
    location = headers.get("location", "")
    record("endpoint", "HTTP redirects to HTTPS", name,
           status in (301, 302, 307, 308) and location.startswith("https://"), f"{status} -> {location or 'none'}")

    status, headers, tls = fetch(base + "/")
    record("endpoint", "TLS 1.2 or newer", name, tls in ("TLSv1.2", "TLSv1.3"), tls or "unknown")
    record("endpoint", "Login required (no credentials)", name, status == 401, f"{status}")
    missing = [h for h in REQUIRED_HEADERS if h.lower() not in headers]
    record("endpoint", "Security headers", name, not missing,
           "all present" if not missing else "missing " + ", ".join(missing))
    server = headers.get("server", "")
    record("endpoint", "Server version hidden", name,
           "/" not in server and "werkzeug" not in server.lower(), server or "no Server header")

    status, _, _ = fetch(base + "/", headers=basic("omnitech:wrong-password"))
    record("endpoint", "Wrong password rejected", name, status == 401, f"{status}")
    if AUTH:
        status, _, _ = fetch(base + "/", headers=basic(AUTH))
        record("endpoint", "Correct login accepted", name, status == 200, f"{status}")

    status, _, _ = fetch(base + "/.env")
    record("endpoint", "Hidden files never served (/.env)", name, status == 404, f"{status}")
    status, _, _ = fetch(base + "/upload-limit-check", method="POST", body=b"x" * (2 * 1024 * 1024),
                         headers={"Content-Type": "application/octet-stream"})
    record("endpoint", "Uploads over 1 MB refused", name, status == 413, f"{status}")


def rate_limit_check(base, total=100, workers=25):
    def one(_):
        try:
            return fetch(base + "/", timeout=30)[0]
        except OSError:
            return 0
    with ThreadPoolExecutor(workers) as pool:
        codes = list(pool.map(one, range(total)))
    limited = codes.count(429)
    record("endpoint", "Rate limiting (10 req/s per caller, burst 40)", "home", limited > 0,
           f"{limited} of {total} parallel requests got 429")


# ── Data security (configuration read back from Azure) ──────────────────────

def az(*args):
    out = subprocess.run(["az", *args, "-o", "json"], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "az failed")
    return json.loads(out.stdout or "null")


def config_checks(deployment):
    rg = deployment["resource_group"]
    sub = az("account", "show")["id"]
    acr_name, kv_name = f"omnitech{sub[:8]}", f"omnitech-kv-{sub[:8]}"
    apps_identity = az("identity", "show", "-n", "omnitech-apps", "-g", rg)
    ci_identity = az("identity", "show", "-n", "omnitech-github-deploy", "-g", rg)

    for name in deployment["services"]:
        app = az("containerapp", "show", "-n", f"omnitech-{name}", "-g", rg)
        cfg = app["properties"]["configuration"]
        containers = app["properties"]["template"]["containers"]
        ingress = cfg["ingress"]
        record("endpoint", "Only the gateway port is exposed, HTTPS only", name,
               ingress["targetPort"] == 8080 and ingress["allowInsecure"] is False
               and any(c["name"] == "gateway" for c in containers),
               f"targetPort {ingress['targetPort']}, allowInsecure {ingress['allowInsecure']}, "
               f"containers {[c['name'] for c in containers]}")
        secrets = cfg.get("secrets") or []
        record("data", "Secrets are Key Vault references (no values in the app)", name,
               secrets and all(s.get("keyVaultUrl") and not s.get("value") for s in secrets),
               ", ".join(f"{s['name']} -> {s.get('keyVaultUrl', 'PLAIN VALUE')}" for s in secrets) or "no secrets")
        regs = cfg.get("registries") or []
        record("data", "Images pulled with managed identity (no registry password)", name,
               regs and all(r.get("identity") and not r.get("passwordSecretRef") for r in regs),
               ", ".join(f"{r['server']} via {r.get('identity', '').rsplit('/', 1)[-1]}" for r in regs))
        ids = list((app.get("identity") or {}).get("userAssignedIdentities") or {})
        record("data", "Runs as the least-privilege app identity", name,
               ids == [apps_identity["id"]] or [i.lower() for i in ids] == [apps_identity["id"].lower()],
               (app.get("identity") or {}).get("type", "none"))
        risky = [e["name"] for c in containers for e in c.get("env") or []
                 if any(w in e["name"].upper() for w in ("PASSWORD", "SECRET", "TOKEN", "KEY"))
                 and "value" in e]
        record("data", "No plain-text secrets in environment variables", name, not risky,
               "none" if not risky else ", ".join(risky))

    acr = az("acr", "show", "-n", acr_name, "-g", rg)
    record("data", "Registry admin account disabled", acr_name, acr["adminUserEnabled"] is False,
           f"adminUserEnabled {acr['adminUserEnabled']}")

    kv = az("keyvault", "show", "-n", kv_name, "-g", rg)["properties"]
    record("data", "Key Vault uses Azure RBAC and soft delete", kv_name,
           kv.get("enableRbacAuthorization") and kv.get("enableSoftDelete") is not False,
           f"RBAC {kv.get('enableRbacAuthorization')}, soft delete {kv.get('enableSoftDelete')}, "
           f"retention {kv.get('softDeleteRetentionInDays')} days")
    names = [s["name"] for s in az("keyvault", "secret", "list", "--vault-name", kv_name)]
    record("data", "Gateway password stored only in Key Vault", kv_name, "gateway-password" in names,
           f"secrets: {', '.join(names)} (values not read by this check)")

    kv_id = az("keyvault", "show", "-n", kv_name, "-g", rg)["id"]

    def roles(principal):
        """Role assignments on the registry and vault, including ones inherited from above."""
        found = set()
        for scope in (acr["id"], kv_id):
            for ra in az("role", "assignment", "list", "--assignee", principal,
                         "--scope", scope, "--include-inherited"):
                found.add((ra["roleDefinitionName"], ra["scope"]))
        return sorted(found)

    rg_scope = f"/subscriptions/{sub}/resourceGroups/{rg}".lower()
    apps_roles = roles(apps_identity["principalId"])
    record("data", "App identity: only AcrPull + Key Vault Secrets User", "omnitech-apps",
           {r for r, _ in apps_roles} == {"AcrPull", "Key Vault Secrets User"},
           "; ".join(f"{r} on {s.rsplit('/', 1)[-1]}" for r, s in apps_roles))
    ci_roles = roles(ci_identity["principalId"])
    record("data", "CI identity scoped to the resource group (not the subscription)", "github-ci",
           all(s.lower().startswith(rg_scope) for _, s in ci_roles),
           "; ".join(f"{r} on {s.rsplit('/', 1)[-1]}" for r, s in ci_roles))


def repo_checks():
    baseline = json.loads((ROOT / ".secrets.baseline").read_text())["results"]
    record("data", "No secrets committed to the repository (detect-secrets)", "repo", not baseline,
           f"{sum(len(v) for v in baseline.values())} findings in .secrets.baseline")
    workflow = (ROOT / ".github" / "workflows" / "cloud-deployment.yml").read_text()
    record("data", "CI logs in with OIDC (no stored Azure credentials)", "repo",
           "id-token: write" in workflow and "AZURE_CREDENTIALS" not in workflow and "client-secret" not in workflow,
           "azure/login with a federated identity; no client secret")
    deploy = (ROOT / "scripts" / "deploy" / "azure" / "deploy.sh").read_text()
    record("data", "Images built only from git-tracked files (no local .env or *.db)", "repo",
           "--exclude-standard" in deploy, "deploy.sh copies `git ls-files` into a clean build folder")


def write_report(deployment):
    passed = sum(r["passed"] for r in results)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (EVIDENCE / "cloud-security-results.json").write_text(json.dumps(
        {"checked_at": stamp, "deployment": deployment, "passed": passed, "total": len(results),
         "results": results}, indent=2) + "\n")
    lines = [
        "# Cloud security report (Azure Container Apps)", "",
        f"- Checked: {stamp} against commit {deployment['commit']}",
        f"- Result: **{passed}/{len(results)} checks passed**", "",
        "Endpoint security: every app sits behind an nginx security gateway sidecar, the only port the "
        "ingress exposes. Data security: the gateway password lives only in Azure Key Vault and apps reach "
        "it, and the image registry, through a least-privilege managed identity.", "",
    ]
    for area, title in (("endpoint", "Endpoint security"), ("data", "Data security")):
        lines += [f"## {title}", "", "| Control | Target | Result | Evidence |", "|---|---|---|---|"]
        lines += [f"| {r['control']} | {r['target']} | {'PASS' if r['passed'] else 'FAIL'} | {r['detail']} |"
                  for r in results if r["area"] == area]
        lines.append("")
    (EVIDENCE / "cloud-security-report.md").write_text("\n".join(lines))
    print(f"{passed}/{len(results)} passed -> {EVIDENCE / 'cloud-security-report.md'}")
    return 0 if passed == len(results) else 1


def main():
    deployment = json.loads((EVIDENCE / "deployment.json").read_text())
    for name, base in deployment["services"].items():
        endpoint_checks(name, base)
    rate_limit_check(deployment["services"]["home"])
    try:
        config_checks(deployment)
    except (RuntimeError, KeyError) as exc:
        record("data", "Read Azure configuration", "azure", False, str(exc))
    repo_checks()
    return write_report(deployment)


if __name__ == "__main__":
    sys.exit(main())
