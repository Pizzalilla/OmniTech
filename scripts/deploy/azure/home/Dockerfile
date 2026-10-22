# Cloud image of the unified home page (locally it is mounted into nginx by docker-compose).
FROM nginx:alpine
COPY shared/frontend /usr/share/nginx/html
COPY scripts/deploy/azure/home/40-omnitech-links.sh /docker-entrypoint.d/40-omnitech-links.sh
RUN chmod +x /docker-entrypoint.d/40-omnitech-links.sh
