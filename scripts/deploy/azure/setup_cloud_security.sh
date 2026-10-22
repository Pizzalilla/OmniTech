#!/usr/bin/env bash
# One-time cloud security setup (needs an Owner login, because it grants roles).
# Run after the first deploy.sh and setup_github_oidc.sh:  bash scripts/deploy/azure/setup_cloud_security.sh
#
# Creates:
#   - Key Vault (RBAC mode, soft delete) holding the gateway login password
#   - user-assigned identity "omnitech-apps" that every app runs as
# Grants only what each identity needs:
#   omnitech-apps          -> AcrPull on the registry, Key Vault Secrets User on the vault
#   omnitech-github-deploy -> Key Vault Secrets User (the CI smoke test logs in with it)
#   you                    -> Key Vault Secrets Officer (to create / rotate the password)
set -euo pipefail
cd "$(dirname "$0")/../../.."
source scripts/deploy/azure/config.sh

SUB_ID=$(az account show --query id -o tsv)
AZ_ACR="${AZ_ACR:-omnitech${SUB_ID:0:8}}"
AZ_KV="${AZ_KV:-omnitech-kv-${SUB_ID:0:8}}"
ME=$(az ad signed-in-user show --query id -o tsv)

grant() {  # principal-id role scope principal-type  (re-running is safe)
  az role assignment create --assignee-object-id "$1" --assignee-principal-type "$4" \
    --role "$2" --scope "$3" -o none
}

echo "==> Key Vault $AZ_KV"
az provider register --namespace Microsoft.KeyVault --wait -o none
az keyvault show -n "$AZ_KV" -g "$AZ_RG" -o none 2>/dev/null \
  || az keyvault create -n "$AZ_KV" -g "$AZ_RG" -l "$AZ_LOCATION" \
       --enable-rbac-authorization true --retention-days 7 -o none
KV_ID=$(az keyvault show -n "$AZ_KV" -g "$AZ_RG" --query id -o tsv)

echo "==> App identity $AZ_APPS_IDENTITY"
az identity show -n "$AZ_APPS_IDENTITY" -g "$AZ_RG" -o none 2>/dev/null \
  || az identity create -n "$AZ_APPS_IDENTITY" -g "$AZ_RG" -l "$AZ_LOCATION" -o none
APPS_PID=$(az identity show -n "$AZ_APPS_IDENTITY" -g "$AZ_RG" --query principalId -o tsv)
CI_PID=$(az identity show -n "$GITHUB_DEPLOY_IDENTITY" -g "$AZ_RG" --query principalId -o tsv 2>/dev/null || true)
ACR_ID=$(az acr show -n "$AZ_ACR" -g "$AZ_RG" --query id -o tsv)

echo "==> Least-privilege role assignments"
grant "$APPS_PID" AcrPull "$ACR_ID" ServicePrincipal
grant "$APPS_PID" "Key Vault Secrets User" "$KV_ID" ServicePrincipal
if [[ -n "$CI_PID" ]]; then
  grant "$CI_PID" "Key Vault Secrets User" "$KV_ID" ServicePrincipal
else
  echo "    $GITHUB_DEPLOY_IDENTITY not found: run setup_github_oidc.sh, then re-run this script"
fi
grant "$ME" "Key Vault Secrets Officer" "$KV_ID" User

echo "==> Registry: admin account off (images are pulled with the identity, no password)"
az acr update -n "$AZ_ACR" --admin-enabled false -o none

echo "==> Gateway password in Key Vault"
# New roles can take a minute to apply; retry until we can read the vault.
for _ in $(seq 1 20); do
  az keyvault secret list --vault-name "$AZ_KV" -o none 2>/dev/null && break
  sleep 10
done
if az keyvault secret show --vault-name "$AZ_KV" -n "$GATEWAY_SECRET" -o none 2>/dev/null; then
  echo "    already set (rotate with: az keyvault secret set --vault-name $AZ_KV -n $GATEWAY_SECRET --value <new>)"
else
  # Random 24-character password, generated here and sent straight to the vault; never printed.
  az keyvault secret set --vault-name "$AZ_KV" -n "$GATEWAY_SECRET" \
    --value "$(openssl rand -base64 18)" --content-type "gateway basic-auth password" -o none
  echo "    created"
fi

echo
echo "Done. Next: bash scripts/deploy/azure/deploy.sh  (puts every app behind the login)"
echo "Login user: $GATEWAY_USER"
echo "See the password (only when you need it):"
echo "  az keyvault secret show --vault-name $AZ_KV -n $GATEWAY_SECRET --query value -o tsv"
