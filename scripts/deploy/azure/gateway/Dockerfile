# Security gateway: runs as a sidecar next to every cloud app and is the only port the
# Container Apps ingress exposes. Adds login, rate limiting, size limits and security headers.
FROM nginx:alpine
RUN apk add --no-cache openssl && rm /etc/nginx/conf.d/default.conf
COPY gateway.conf.template /etc/nginx/templates/gateway.conf.template
COPY 15-gateway-auth.sh /docker-entrypoint.d/15-gateway-auth.sh
RUN chmod +x /docker-entrypoint.d/15-gateway-auth.sh
ENV APP_PORT=5000
EXPOSE 8080
