#!/bin/sh
# Runs when the nginx container starts: point the home page's localhost links at the cloud URLs.
for n in 1 2 3 4 5; do
  eval "url=\${STUDENT${n}_URL:-}"
  if [ -n "$url" ]; then
    sed -i -e "s#http://localhost:500${n}#${url}#g" -e "s#Open on port 500${n}#Open#g" /usr/share/nginx/html/*.html
  fi
done
# AI-Mode is disabled by default in the cloud deployment.
sed -i 's#Ollama is at <a href="http://localhost:11434">localhost:11434</a>#AI services are disabled in this cloud deployment#' \
  /usr/share/nginx/html/index.html
