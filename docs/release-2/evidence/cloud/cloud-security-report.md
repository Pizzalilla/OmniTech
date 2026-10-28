# Cloud security report (Azure Container Apps)

- Checked: 2026-10-28T02:19:03+00:00 against commit c4f96ec
- Result: **93/93 checks passed**

Endpoint security: every app sits behind an nginx security gateway sidecar, the only port the ingress exposes. Data security: the gateway password lives only in Azure Key Vault and apps reach it, and the image registry, through a least-privilege managed identity.

## Endpoint security

| Control | Target | Result | Evidence |
|---|---|---|---|
| HTTP redirects to HTTPS | home | PASS | 301 -> https://omnitech-home.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/ |
| TLS 1.2 or newer | home | PASS | TLSv1.3 |
| Login required (no credentials) | home | PASS | 401 |
| Security headers | home | PASS | all present |
| Server version hidden | home | PASS | nginx |
| Wrong password rejected | home | PASS | 401 |
| Correct login accepted | home | PASS | 200 |
| Hidden files never served (/.env) | home | PASS | 404 |
| Uploads over 1 MB refused | home | PASS | 413 |
| HTTP redirects to HTTPS | student-1 | PASS | 301 -> https://omnitech-student-1.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/ |
| TLS 1.2 or newer | student-1 | PASS | TLSv1.3 |
| Login required (no credentials) | student-1 | PASS | 401 |
| Security headers | student-1 | PASS | all present |
| Server version hidden | student-1 | PASS | nginx |
| Wrong password rejected | student-1 | PASS | 401 |
| Correct login accepted | student-1 | PASS | 200 |
| Hidden files never served (/.env) | student-1 | PASS | 404 |
| Uploads over 1 MB refused | student-1 | PASS | 413 |
| HTTP redirects to HTTPS | student-2 | PASS | 301 -> https://omnitech-student-2.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/ |
| TLS 1.2 or newer | student-2 | PASS | TLSv1.3 |
| Login required (no credentials) | student-2 | PASS | 401 |
| Security headers | student-2 | PASS | all present |
| Server version hidden | student-2 | PASS | nginx |
| Wrong password rejected | student-2 | PASS | 401 |
| Correct login accepted | student-2 | PASS | 200 |
| Hidden files never served (/.env) | student-2 | PASS | 404 |
| Uploads over 1 MB refused | student-2 | PASS | 413 |
| HTTP redirects to HTTPS | student-3 | PASS | 301 -> https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/ |
| TLS 1.2 or newer | student-3 | PASS | TLSv1.3 |
| Login required (no credentials) | student-3 | PASS | 401 |
| Security headers | student-3 | PASS | all present |
| Server version hidden | student-3 | PASS | nginx |
| Wrong password rejected | student-3 | PASS | 401 |
| Correct login accepted | student-3 | PASS | 200 |
| Hidden files never served (/.env) | student-3 | PASS | 404 |
| Uploads over 1 MB refused | student-3 | PASS | 413 |
| HTTP redirects to HTTPS | student-4 | PASS | 301 -> https://omnitech-student-4.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/ |
| TLS 1.2 or newer | student-4 | PASS | TLSv1.3 |
| Login required (no credentials) | student-4 | PASS | 401 |
| Security headers | student-4 | PASS | all present |
| Server version hidden | student-4 | PASS | nginx |
| Wrong password rejected | student-4 | PASS | 401 |
| Correct login accepted | student-4 | PASS | 200 |
| Hidden files never served (/.env) | student-4 | PASS | 404 |
| Uploads over 1 MB refused | student-4 | PASS | 413 |
| HTTP redirects to HTTPS | student-5 | PASS | 301 -> https://omnitech-student-5.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/ |
| TLS 1.2 or newer | student-5 | PASS | TLSv1.3 |
| Login required (no credentials) | student-5 | PASS | 401 |
| Security headers | student-5 | PASS | all present |
| Server version hidden | student-5 | PASS | nginx |
| Wrong password rejected | student-5 | PASS | 401 |
| Correct login accepted | student-5 | PASS | 200 |
| Hidden files never served (/.env) | student-5 | PASS | 404 |
| Uploads over 1 MB refused | student-5 | PASS | 413 |
| Rate limiting (10 req/s per caller, burst 40) | home | PASS | 41 of 100 parallel requests got 429 |
| Only the gateway port is exposed, HTTPS only | home | PASS | targetPort 8080, allowInsecure False, containers ['app', 'gateway'] |
| Only the gateway port is exposed, HTTPS only | student-1 | PASS | targetPort 8080, allowInsecure False, containers ['app', 'gateway'] |
| Only the gateway port is exposed, HTTPS only | student-2 | PASS | targetPort 8080, allowInsecure False, containers ['app', 'gateway'] |
| Only the gateway port is exposed, HTTPS only | student-3 | PASS | targetPort 8080, allowInsecure False, containers ['app', 'gateway'] |
| Only the gateway port is exposed, HTTPS only | student-4 | PASS | targetPort 8080, allowInsecure False, containers ['app', 'gateway'] |
| Only the gateway port is exposed, HTTPS only | student-5 | PASS | targetPort 8080, allowInsecure False, containers ['app', 'gateway'] |

## Data security

| Control | Target | Result | Evidence |
|---|---|---|---|
| Secrets are Key Vault references (no values in the app) | home | PASS | gateway-password -> https://omnitech-kv-f8fb3a40.vault.azure.net/secrets/gateway-password |
| Images pulled with managed identity (no registry password) | home | PASS | omnitechf8fb3a40.azurecr.io via omnitech-apps |
| Runs as the least-privilege app identity | home | PASS | UserAssigned |
| No plain-text secrets in environment variables | home | PASS | none |
| Secrets are Key Vault references (no values in the app) | student-1 | PASS | gateway-password -> https://omnitech-kv-f8fb3a40.vault.azure.net/secrets/gateway-password |
| Images pulled with managed identity (no registry password) | student-1 | PASS | omnitechf8fb3a40.azurecr.io via omnitech-apps |
| Runs as the least-privilege app identity | student-1 | PASS | UserAssigned |
| No plain-text secrets in environment variables | student-1 | PASS | none |
| Secrets are Key Vault references (no values in the app) | student-2 | PASS | gateway-password -> https://omnitech-kv-f8fb3a40.vault.azure.net/secrets/gateway-password |
| Images pulled with managed identity (no registry password) | student-2 | PASS | omnitechf8fb3a40.azurecr.io via omnitech-apps |
| Runs as the least-privilege app identity | student-2 | PASS | UserAssigned |
| No plain-text secrets in environment variables | student-2 | PASS | none |
| Secrets are Key Vault references (no values in the app) | student-3 | PASS | gateway-password -> https://omnitech-kv-f8fb3a40.vault.azure.net/secrets/gateway-password |
| Images pulled with managed identity (no registry password) | student-3 | PASS | omnitechf8fb3a40.azurecr.io via omnitech-apps |
| Runs as the least-privilege app identity | student-3 | PASS | UserAssigned |
| No plain-text secrets in environment variables | student-3 | PASS | none |
| Secrets are Key Vault references (no values in the app) | student-4 | PASS | gateway-password -> https://omnitech-kv-f8fb3a40.vault.azure.net/secrets/gateway-password |
| Images pulled with managed identity (no registry password) | student-4 | PASS | omnitechf8fb3a40.azurecr.io via omnitech-apps |
| Runs as the least-privilege app identity | student-4 | PASS | UserAssigned |
| No plain-text secrets in environment variables | student-4 | PASS | none |
| Secrets are Key Vault references (no values in the app) | student-5 | PASS | gateway-password -> https://omnitech-kv-f8fb3a40.vault.azure.net/secrets/gateway-password |
| Images pulled with managed identity (no registry password) | student-5 | PASS | omnitechf8fb3a40.azurecr.io via omnitech-apps |
| Runs as the least-privilege app identity | student-5 | PASS | UserAssigned |
| No plain-text secrets in environment variables | student-5 | PASS | none |
| Registry admin account disabled | omnitechf8fb3a40 | PASS | adminUserEnabled False |
| Key Vault uses Azure RBAC and soft delete | omnitech-kv-f8fb3a40 | PASS | RBAC True, soft delete True, retention 7 days |
| Gateway password stored only in Key Vault | omnitech-kv-f8fb3a40 | PASS | secrets: gateway-password (values not read by this check) |
| App identity: only AcrPull + Key Vault Secrets User | omnitech-apps | PASS | AcrPull on omnitechf8fb3a40; Key Vault Secrets User on omnitech-kv-f8fb3a40 |
| CI identity scoped to the resource group (not the subscription) | github-ci | PASS | Contributor on omnitech-rg; Key Vault Secrets User on omnitech-kv-f8fb3a40 |
| No secrets committed to the repository (detect-secrets) | repo | PASS | 0 findings in .secrets.baseline |
| CI logs in with OIDC (no stored Azure credentials) | repo | PASS | azure/login with a federated identity; no client secret |
| Images built only from git-tracked files (no local .env or *.db) | repo | PASS | deploy.sh copies `git ls-files` into a clean build folder |
