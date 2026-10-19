#!/usr/bin/env bash
# One-time setup so cloud-deployment.yml can deploy to Azure without any stored password:
# GitHub proves its identity to Azure with a short-lived OIDC token for this repo's main branch.
# Run after the first successful deploy.sh (the resource group must exist).
set -euo pipefail
cd "$(dirname "$0")/../../.."
source scripts/deploy/azure/config.sh
REPO="${GITHUB_REPO:-Pizzalilla/OmniTech}"
APP_NAME="omnitech-github-deploy"

SUB_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
RG_ID=$(az group show -n "$AZ_RG" --query id -o tsv)

APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [[ -z "$APP_ID" ]]; then
  APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
  az ad sp create --id "$APP_ID" -o none
fi

for ref in "refs/heads/main"; do
  cred_name="github-${ref//\//-}"
  az ad app federated-credential list --id "$APP_ID" --query "[?name=='$cred_name']" -o tsv | grep -q . \
    || az ad app federated-credential create --id "$APP_ID" --parameters "{
         \"name\": \"$cred_name\",
         \"issuer\": \"https://token.actions.githubusercontent.com\",
         \"subject\": \"repo:$REPO:ref:$ref\",
         \"audiences\": [\"api://AzureADTokenExchange\"]
       }" -o none
done

# Contributor on the project's resource group only (not the whole subscription).
az role assignment create --assignee "$APP_ID" --role Contributor --scope "$RG_ID" -o none 2>/dev/null || true

echo
echo "Add these as GitHub repository VARIABLES (Settings > Secrets and variables > Actions > Variables)."
echo "They are identifiers, not passwords:"
echo "  AZURE_CLIENT_ID=$APP_ID"
echo "  AZURE_TENANT_ID=$TENANT_ID"
echo "  AZURE_SUBSCRIPTION_ID=$SUB_ID"
