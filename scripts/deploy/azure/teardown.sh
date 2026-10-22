#!/usr/bin/env bash
# Delete everything the deployment created (stops all Azure charges). Re-deploy any time with deploy.sh.
set -euo pipefail
cd "$(dirname "$0")/../../.."
source scripts/deploy/azure/config.sh
read -r -p "Delete resource group '$AZ_RG' and everything in it? [y/N] " answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Cancelled."; exit 0; }
az group delete -n "$AZ_RG" --yes --no-wait
echo "Deleting $AZ_RG in the background (takes a few minutes)."
