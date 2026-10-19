# Cloud deployment (Azure Container Apps)

The integrated app (home page + the five student services) runs on Azure Container
Apps. Release 2 baseline: **AI-Mode, MCP, RAG and the Multi-Agent Server are disabled
by default** in the cloud. Ollama is not deployed, and every AI address points to a
non-resolving `.invalid` host, so each feature must fall back gracefully and keep its
CRUD working.

| File | Purpose |
|---|---|
| `scripts/deploy/azure/config.sh` | Region, names, services, cloud environment variables |
| `scripts/deploy/azure/deploy.sh` | Creates or updates everything; builds the images with Docker and pushes them to the registry |
| `scripts/deploy/azure/smoke_test.py` | Checks every service and writes the cloud deployment report |
| `scripts/deploy/azure/setup_github_oidc.sh` | One-time: lets GitHub Actions deploy without stored passwords |
| `scripts/deploy/azure/teardown.sh` | Deletes everything (stops all charges) |
| `.github/workflows/cloud-deployment.yml` | Runs all five student workflows, then deploys and smoke-tests |

## What gets created

One resource group (`omnitech-rg`) containing an Azure Container Registry (Basic), a
Container Apps environment and six container apps (`omnitech-home`,
`omnitech-student-1` … `5`). Each app has HTTPS ingress, 0.25 vCPU / 0.5 GiB, and
scales to zero when idle (the first request after idle takes ~20–60 s). Images are
pulled with each app's managed identity, so there are no registry passwords.
Each feature's SQLite data lives inside its container and is re-seeded on restart.

## First deployment (one person, from a terminal)

1. Activate **Azure for Students** (UTS email, no credit card).
2. Install the Azure CLI: `brew install azure-cli`, then `az login`. Start Docker Desktop:
   Azure for Students blocks cloud builds (ACR Tasks), so images are built locally for
   `linux/amd64` and pushed.
3. Deploy and check it:
   ```bash
   bash scripts/deploy/azure/deploy.sh
   python3 scripts/deploy/azure/smoke_test.py
   ```
   If your subscription only allows certain regions, set one first:
   `export AZ_LOCATION=southeastasia`.
4. Let GitHub deploy: `bash scripts/deploy/azure/setup_github_oidc.sh`, then add the three
   printed values as repository **variables** (Settings → Secrets and variables → Actions
   → Variables): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.

## After that (anyone)

GitHub → Actions → **Cloud Deployment (Azure)** → Run workflow. It also runs on every push
to `main`. The deploy job only starts after all five student workflows pass, and the
cloud deployment report is attached to the run as the `cloud-deployment-evidence` artifact.

## Evidence for the report

`docs/release-2/evidence/cloud/`:
- `deployment.json`: what was deployed, where, and from which commit
- `cloud-deployment-report.md`: smoke test results, ending with the **final human release
  decision**, filled in after the agentic-loop Cloud Deployment Review
- `cloud-smoke-results.json`: the same results for the Cloud Deployment Review mode

## For each student

- Your feature must keep working with the cloud settings in `config.sh`: AI calls fail
  fast and your page and CRUD still work. To test locally:
  `source scripts/deploy/azure/config.sh && env "${AI_DISABLED_ENV[@]}" python <your app>`.
- Use `HOME_URL` for "back to home" links instead of `http://localhost:8080`.
- Add one or two checks for your own feature to `CHECKS` in `smoke_test.py`.

## Costs

Covered by the $100 Azure for Students credit; with scale-to-zero the container apps
fall mostly inside the free monthly allowance, and the registry is about US$0.17/day.
Run `teardown.sh` after the final showcase.
