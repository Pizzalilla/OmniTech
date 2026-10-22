#!/usr/bin/env bash
# Deploy the integrated OmniTech application to Azure Container Apps.
# Safe to re-run: creates what is missing, otherwise rolls out a new image.
#   bash scripts/deploy/azure/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/../../.."
source scripts/deploy/azure/config.sh

az account show -o none 2>/dev/null || { echo "Not logged in to Azure. Run: az login"; exit 1; }
# Images are built with Docker and pushed (Azure for Students blocks cloud builds via ACR Tasks).
docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and re-run."; exit 1; }
SUB_ID=$(az account show --query id -o tsv)
# Registry names must be globally unique and alphanumeric; derive one from the subscription.
AZ_ACR="${AZ_ACR:-omnitech${SUB_ID:0:8}}"

echo "==> Subscription $(az account show --query name -o tsv), region $AZ_LOCATION, tag $IMAGE_TAG"
az extension add --name containerapp --upgrade --only-show-errors -y
# One-time subscription setup; skipped in CI, where the deploy identity only has the resource group.
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry; do
  state=$(az provider show -n "$ns" --query registrationState -o tsv 2>/dev/null || echo unknown)
  [[ "$state" == "Registered" ]] || az provider register --namespace "$ns" --wait -o none \
    || echo "    (could not register $ns; fine if it is already registered)"
done

echo "==> Resource group, registry and Container Apps environment"
az group show -n "$AZ_RG" -o none 2>/dev/null || az group create -n "$AZ_RG" -l "$AZ_LOCATION" -o none
az acr show -n "$AZ_ACR" -g "$AZ_RG" -o none 2>/dev/null \
  || az acr create -n "$AZ_ACR" -g "$AZ_RG" --sku Basic --admin-enabled false -o none
# WorkloadProfiles (Consumption profile, pay-per-use): the default "Express" mode cannot
# pull images with a managed identity.
az containerapp env show -n "$AZ_ENV" -g "$AZ_RG" -o none 2>/dev/null \
  || az containerapp env create -n "$AZ_ENV" -g "$AZ_RG" -l "$AZ_LOCATION" \
       --environment-mode WorkloadProfiles -o none
ENV_MODE=$(az containerapp env show -n "$AZ_ENV" -g "$AZ_RG" --query properties.environmentMode -o tsv)
[[ "$ENV_MODE" != "Express" ]] || { echo "$AZ_ENV is an Express environment; delete it and re-run."; exit 1; }
DOMAIN=$(az containerapp env show -n "$AZ_ENV" -g "$AZ_RG" --query properties.defaultDomain -o tsv)
REGISTRY="$AZ_ACR.azurecr.io"
ENV_ID=$(az containerapp env show -n "$AZ_ENV" -g "$AZ_RG" --query id -o tsv)
PROFILE=$(az containerapp env show -n "$AZ_ENV" -g "$AZ_RG" \
  --query "properties.workloadProfiles[?workloadProfileType=='Consumption'].name | [0]" -o tsv)

# Cloud security: apps run as one user-assigned identity that may only pull images and
# read the gateway password from Key Vault. Created once by setup_cloud_security.sh.
AZ_KV="${AZ_KV:-omnitech-kv-${SUB_ID:0:8}}"
APPS_ID=$(az identity show -n "$AZ_APPS_IDENTITY" -g "$AZ_RG" --query id -o tsv 2>/dev/null || true)
KV_URI=$(az keyvault show -n "$AZ_KV" -g "$AZ_RG" --query properties.vaultUri -o tsv 2>/dev/null || true)
[[ -n "$APPS_ID" && -n "$KV_URI" ]] \
  || { echo "Cloud security is not set up. Run: bash scripts/deploy/azure/setup_cloud_security.sh"; exit 1; }

az acr login -n "$AZ_ACR" --only-show-errors
url() { echo "https://omnitech-$1.$DOMAIN"; }

LINK_ENV=("HOME_URL=$(url home)")
for n in 1 2 3 4 5; do LINK_ENV+=("STUDENT${n}_URL=$(url "student-$n")"); done

# Build only from files git would commit: ignored files (.env, local *.db databases with
# real chat data, virtualenvs) can never end up inside an image.
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT
git ls-files -z --cached --others --exclude-standard | while IFS= read -r -d '' f; do
  if [[ -f "$f" ]]; then printf '%s\0' "$f"; fi
done | tar --null -T - -cf - | tar -xf - -C "$BUILD_DIR"

build_push() {  # image dockerfile context
  docker build --platform linux/amd64 -t "$1" -f "$BUILD_DIR/$2" "$BUILD_DIR/$3"
  docker push "$1"
}

GATEWAY_IMAGE="$REGISTRY/omnitech-gateway:$IMAGE_TAG"
echo "==> Security gateway: building and pushing $GATEWAY_IMAGE"
build_push "$GATEWAY_IMAGE" scripts/deploy/azure/gateway/Dockerfile scripts/deploy/azure/gateway

# Container App definition: the feature container plus the gateway sidecar. Only the
# gateway port is exposed, over HTTPS only; the password comes from Key Vault by reference.
app_yaml() {  # image port env...
  local image=$1 port=$2; shift 2
  cat <<YAML
location: $AZ_LOCATION
identity:
  type: UserAssigned
  userAssignedIdentities:
    "$APPS_ID": {}
properties:
  environmentId: $ENV_ID
  workloadProfileName: $PROFILE
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: $GATEWAY_PORT
      allowInsecure: false
      transport: auto
    registries:
      - server: $REGISTRY
        identity: $APPS_ID
    secrets:
      - name: $GATEWAY_SECRET
        keyVaultUrl: ${KV_URI}secrets/$GATEWAY_SECRET
        identity: $APPS_ID
  template:
    containers:
      - name: app
        image: $image
        resources:
          cpu: 0.25
          memory: 0.5Gi
        env:
YAML
  local kv
  for kv in "$@"; do
    printf '          - name: %s\n            value: "%s"\n' "${kv%%=*}" "${kv#*=}"
  done
  cat <<YAML
      - name: gateway
        image: $GATEWAY_IMAGE
        resources:
          cpu: 0.25
          memory: 0.5Gi
        env:
          - name: APP_PORT
            value: "$port"
          - name: GATEWAY_USER
            value: "$GATEWAY_USER"
          - name: GATEWAY_PASSWORD
            secretRef: $GATEWAY_SECRET
    scale:
      minReplicas: 0
      maxReplicas: 1
YAML
}

for spec in "${SERVICES[@]}"; do
  IFS="|" read -r name context dockerfile port <<< "$spec"
  app="omnitech-$name"
  image="$REGISTRY/omnitech-$name:$IMAGE_TAG"
  if [[ "$name" == "home" ]]; then env_vars=("${LINK_ENV[@]}"); else env_vars=("${AI_DISABLED_ENV[@]}" "${LINK_ENV[@]}"); fi

  echo "==> $app: building and pushing $image"
  # Azure runs amd64; --platform also makes Apple-silicon Macs build the right architecture.
  build_push "$image" "$dockerfile" "$context"

  app_yaml "$image" "$port" "${env_vars[@]}" > "$BUILD_DIR/$app.yaml"
  if az containerapp show -n "$app" -g "$AZ_RG" -o none 2>/dev/null; then
    echo "==> $app: rolling out new revision"
    az containerapp update -n "$app" -g "$AZ_RG" --yaml "$BUILD_DIR/$app.yaml" -o none
  else
    echo "==> $app: creating"
    az containerapp create -n "$app" -g "$AZ_RG" --yaml "$BUILD_DIR/$app.yaml" -o none
  fi
done

mkdir -p docs/release-2/evidence/cloud
{
  echo "{"
  echo "  \"deployed_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"commit\": \"$(git rev-parse --short HEAD)\","
  echo "  \"image_tag\": \"$IMAGE_TAG\","
  echo "  \"resource_group\": \"$AZ_RG\","
  echo "  \"region\": \"$AZ_LOCATION\","
  echo "  \"services\": {"
  sep=""
  for spec in "${SERVICES[@]}"; do
    IFS="|" read -r name _ _ _ <<< "$spec"
    printf '%s    "%s": "%s"' "$sep" "$name" "$(url "$name")"
    sep=$',\n'
  done
  echo ""
  echo "  }"
  echo "}"
} > docs/release-2/evidence/cloud/deployment.json

echo "==> Deployed. Home page: $(url home)"
echo "    Service URLs saved to docs/release-2/evidence/cloud/deployment.json"
