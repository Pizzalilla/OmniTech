"""Check the Azure deployment and write the cloud deployment report.

Usage: SMOKE_AUTH=user:password python scripts/deploy/azure/smoke_test.py
Every app is behind the security gateway, so the checks log in with SMOKE_AUTH
(in CI the workflow reads the password from Azure Key Vault; nothing is stored).
Reads service URLs from docs/release-2/evidence/cloud/deployment.json (written by
deploy.sh) and writes cloud-deployment-report.md + cloud-smoke-results.json next to it.
Each student can add checks for their own feature to CHECKS below.
"""

import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[3] / "docs" / "release-2" / "evidence" / "cloud"
COLD_START_WAIT = 150  # apps scale to zero, so the first request can take a while
AUTH = os.getenv("SMOKE_AUTH", "")
AUTH_HEADER = {"Authorization": "Basic " + base64.b64encode(AUTH.encode()).decode()} if AUTH else {}

# python.org builds on macOS ship without root certificates; use certifi's bundle when present.
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

# service -> list of (description, method, path, json body or None, expected status, text expected in body)
CHECKS = {
    "home": [("Home page lists every feature", "GET", "/", None, 200, "omnitech-student-3")],
    "student-1": [("Catalog page", "GET", "/", None, 200, None),
                  ("Read products", "GET", "/api/products", None, 200, None),
                  ("AI summary disabled by default", "POST", "/api/products/1/ai-summary", None, 503, "unavailable"),
                  ("Multi-Agent disabled by default", "GET", "/api/multi-agent/history", None, 503, "disabled")],
    "student-2": [("Customers page", "GET", "/", None, 200, None),
                  ("Read customers", "GET", "/api/customers", None, 200, None)],
    "student-3": [("Consultant page", "GET", "/", None, 200, None),
                  ("Create session", "POST", "/api/sessions", {"title": "Cloud smoke test"}, 201, "Cloud smoke test"),
                  ("Read sessions", "GET", "/api/sessions", None, 200, "Cloud smoke test"),
                  ("AI services disabled by default", "POST", "/api/rag/query", {"query": "return policy"}, 200, "disabled"),
                  ("Multi-Agent disabled by default", "GET", "/api/multi-agent/history", None, 503, "disabled")],
    "student-4": [("Cart page", "GET", "/", None, 200, None)],
    "student-5": [("Warranty page", "GET", "/", None, 200, None),
                  ("Read tickets", "GET", "/tickets", None, 200, None)],
}


def request(method, url, body, timeout, auth=True):
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"refusing non-HTTP URL: {url}")
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if auth:
        headers.update(AUTH_HEADER)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)  # noqa: S310 - scheme checked above
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:  # noqa: S310 - scheme checked above
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode(errors="replace")


def wake(url):
    """Return None once the service answers, or the last error if it never does."""
    deadline, error = time.time() + COLD_START_WAIT, "timed out"
    while time.time() < deadline:
        try:
            request("GET", url, None, timeout=30, auth=False)
            return None
        except (urllib.error.URLError, TimeoutError) as err:
            error = str(getattr(err, "reason", err))
            time.sleep(5)
    return error


def main():
    deployment = json.loads((EVIDENCE / "deployment.json").read_text())
    if not AUTH:
        print("SMOKE_AUTH is not set; the security gateway will answer 401 to every check.\n"
              "  export SMOKE_AUTH=omnitech:$(az keyvault secret show --vault-name <vault> "
              "-n gateway-password --query value -o tsv)", file=sys.stderr)
    results = []
    for service, checks in CHECKS.items():
        base = deployment["services"].get(service)
        if not base:
            continue
        wake_error = wake(base + "/")
        for desc, method, path, body, want, text in checks:
            start = time.time()
            try:
                status, page = (0, f"service did not start: {wake_error}") if wake_error \
                    else request(method, base + path, body, timeout=60)
            except (urllib.error.URLError, TimeoutError) as err:
                status, page = 0, str(getattr(err, "reason", err))
            ok = status == want and (text is None or text in page)
            results.append({"service": service, "check": desc, "method": method, "url": base + path,
                            "expected": want, "status": status, "passed": ok,
                            "ms": round((time.time() - start) * 1000)})
            reason = "" if ok or status else f"  [{page[:120]}]"
            print(f"{'PASS' if ok else 'FAIL'}  {service:10} {desc} ({method} {path} -> {status}){reason}", flush=True)

    passed = sum(r["passed"] for r in results)
    (EVIDENCE / "cloud-smoke-results.json").write_text(json.dumps(
        {"deployment": deployment, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "passed": passed, "total": len(results), "results": results}, indent=2) + "\n")

    lines = [
        "# Cloud deployment report (Azure Container Apps)", "",
        f"- Deployed: {deployment['deployed_at']} (commit {deployment['commit']}, image tag {deployment['image_tag']})",
        f"- Region / resource group: {deployment['region']} / {deployment['resource_group']}",
        f"- Home page: {deployment['services'].get('home', 'n/a')}",
        f"- Smoke test: **{passed}/{len(results)} checks passed**", "",
        "AI-Mode, MCP, RAG and the Multi-Agent Server are **disabled by default** in this deployment "
        "(Ollama is not deployed and every AI address points to a non-resolving `.invalid` host).",
        "Every app is behind the security gateway; these checks log in. "
        "See `cloud-security-report.md` for the security validation.", "",
        "| Service | Check | Request | Expected | Got | Result | Time |", "|---|---|---|---|---|---|---|",
    ]
    lines += [f"| {r['service']} | {r['check']} | `{r['method']} {r['url']}` | {r['expected']} | {r['status']} | "
              f"{'PASS' if r['passed'] else 'FAIL'} | {r['ms']} ms |" for r in results]
    lines += ["", "## Final human release decision", "",
              "Filled in after the agentic-loop Cloud Deployment Review:", "",
              "- Decision (approve / approve with conditions / reject):",
              "- Decided by:", "- Date:", "- Reason:"]
    (EVIDENCE / "cloud-deployment-report.md").write_text("\n".join(lines) + "\n")
    print(f"{passed}/{len(results)} passed -> {EVIDENCE / 'cloud-deployment-report.md'}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
