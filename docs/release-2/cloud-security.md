# Cloud security (bonus): endpoint and data security

Applies to every app in the Azure deployment (`omnitech-home`, `omnitech-student-1` … `5`).
Validation evidence: `docs/release-2/evidence/cloud/cloud-security-report.md`, written by
`scripts/deploy/azure/security_check.py` on every cloud deployment.

## Endpoint security: protecting the exposed frontend and API endpoints

Every Container App runs two containers: the feature, and an **nginx security gateway**
sidecar (`scripts/deploy/azure/gateway/`). The ingress only exposes the gateway's port
(8080), so nobody can reach a feature's port directly.

| Control | How | Validated by |
|---|---|---|
| HTTPS only | Ingress `allowInsecure: false`; plain HTTP is redirected to HTTPS; TLS 1.2+ | HTTP request gets a redirect to `https://`; TLS version recorded |
| Login on every page and API | HTTP Basic authentication in the gateway, over HTTPS only. The gateway strips the `Authorization` header so the apps never see the password | No login and a wrong password both get 401; the right login gets 200 |
| Rate limiting | 10 requests/second per caller (bursts of 40), applied before the login check, so password guessing is throttled too | 100 parallel requests: the extras get 429 |
| Upload size limit | `client_max_body_size 1m` | A 2 MB POST gets 413 |
| Security headers | HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy` | All present on every response |
| No hidden files | Any path with a `.` segment (`/.env`, `/.git`) returns 404 | `/.env` gets 404 |
| Fewer clues for attackers | nginx version hidden, the apps' `Server` (Werkzeug) header removed, only normal HTTP methods allowed (TRACE gets 405) | `Server` header checked |
| Fails closed | The gateway refuses to start if the password is missing, so an app is never left open | `15-gateway-auth.sh` |

## Data security: application data, secrets, credentials and stored data

| Control | How | Validated by |
|---|---|---|
| Password only in Key Vault | `setup_cloud_security.sh` generates a random password straight into Azure Key Vault (RBAC mode, soft delete). It is never printed, committed or stored in GitHub | The vault holds `gateway-password` |
| Secrets passed by reference | Each app's secret is a Key Vault reference read with its managed identity; the value never appears in the app definition or in environment variables | Every app secret has a `keyVaultUrl`; no plain-text secret env vars |
| No registry password | Registry admin account disabled; apps pull images with the managed identity | `adminUserEnabled: false`; registries use the identity |
| Least privilege | App identity `omnitech-apps`: only **AcrPull** + **Key Vault Secrets User**. CI identity: Contributor on the resource group only (not the subscription) plus Key Vault Secrets User | Role assignments read back from Azure |
| No stored CI credentials | GitHub Actions logs in with OIDC (short-lived token, federated identity). The smoke test reads the gateway password from Key Vault at run time and masks it in the logs | Workflow has `id-token: write` and no client secret |
| No secrets in the code | Pre-commit `detect-secrets` blocks commits containing secrets | `.secrets.baseline` has 0 findings |
| Stored data stays private | Images are built only from git-tracked files, so local SQLite databases (real chat history), `.env` files and virtualenvs are never copied into images. Each app's SQLite database lives inside its container, is not exposed on any port and is reached only through the authenticated HTTPS gateway. Azure encrypts the registry and platform storage at rest | `deploy.sh` builds from `git ls-files` |
| Data in transit | HTTPS to every app; images pushed to the registry over TLS | HTTPS checks above |

## Using it

- One-time (needs an Owner login, because it grants roles):
  `bash scripts/deploy/azure/setup_cloud_security.sh`
- Then deploy as normal: `bash scripts/deploy/azure/deploy.sh`, or push to `main`.
- Log in to the cloud app with user `omnitech`. See the password only when needed:
  `az keyvault secret show --vault-name omnitech-kv-<first 8 of subscription id> -n gateway-password --query value -o tsv`
- Rotate it: `az keyvault secret set --vault-name … -n gateway-password --value <new>`. Apps pick it up within 30 minutes, or on the next deploy.
- Run the validation locally:
  `SMOKE_AUTH=omnitech:<password> python3 scripts/deploy/azure/security_check.py`

## Known limits

- One shared login for the whole team; there are no per-user accounts. Azure's built-in sign-in (Entra ID) would need an app registration, which the UTS tenant blocks for students.
- The browser asks for the login once per app, because each app has its own address.
- Key Vault purge protection is off so the project can be torn down cleanly after marking.
