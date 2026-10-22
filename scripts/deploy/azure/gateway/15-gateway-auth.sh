#!/bin/sh
# Builds the login file from the password Container Apps injects from Azure Key Vault.
# Fails closed: without a password the container does not start, so no app is ever left open.
set -eu
: "${GATEWAY_USER:?GATEWAY_USER is not set}"
: "${GATEWAY_PASSWORD:?GATEWAY_PASSWORD is not set (Key Vault secret missing?)}"
umask 027
printf '%s:%s\n' "$GATEWAY_USER" "$(printf '%s' "$GATEWAY_PASSWORD" | openssl passwd -apr1 -stdin)" \
  > /etc/nginx/.htpasswd
chgrp nginx /etc/nginx/.htpasswd
echo "gateway: login enabled for user '$GATEWAY_USER', proxying to 127.0.0.1:$APP_PORT"
