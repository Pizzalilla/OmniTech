#!/usr/bin/env bash
# One-time setup so cloud-deployment.yml can deploy to Azure without any stored password:
# GitHub proves its identity to Azure with a short-lived OIDC token for this repo's main branch.
# Uses a user-assigned managed identity (an ordinary Azure resource), because student tenants
# usually block creating app registrations. Run after the first successful deploy.sh.
set -euo pipefail
cd "$(dirname "$0")/../../.."
source scripts/deploy/azure/config.sh
REPO="${GITHUB_REPO:-Pizzalilla/OmniTech}"
IDENTITY="omnitech-github-deploy"

SUB_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
RG_ID=$(az group show -n "$AZ_RG" --query id -o tsv)

az identity show -n "$IDENTITY" -g "$AZ_RG" -o none 2>/dev/null \
  || az identity create -n "$IDENTITY" -g "$AZ_RG" -l "$AZ_LOCATION" -o none
CLIENT_ID=$(az identity show -n "$IDENTITY" -g "$AZ_RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -n "$IDENTITY" -g "$AZ_RG" --query principalId -o tsv)

# Only workflow runs on this repo's main branch can use the identity.
az identity federated-credential show -n github-main --identity-name "$IDENTITY" -g "$AZ_RG" -o none 2>/dev/null \
  || az identity federated-credential create -n github-main --identity-name "$IDENTITY" -g "$AZ_RG" \
       --issuer "https://token.actions.githubusercontent.com" \
       --subject "repo:$REPO:ref:refs/heads/main" \
       --audiences "api://AzureADTokenExchange" -o none

# Contributor on the project's resource group only (not the whole subscription).
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$RG_ID" -o none 2>/dev/null || true

echo
echo "Add these as GitHub repository VARIABLES (Settings > Secrets and variables > Actions > Variables)."
echo "They are identifiers, not passwords:"
echo "  AZURE_CLIENT_ID=$CLIENT_ID"
echo "  AZURE_TENANT_ID=$TENANT_ID"
echo "  AZURE_SUBSCRIPTION_ID=$SUB_ID"
