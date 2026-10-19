#!/bin/sh
# Runs when the nginx container starts: point the home page's localhost links at the cloud URLs.
for n in 1 2 3 4 5; do
  eval "url=\${STUDENT${n}_URL:-}"
  if [ -n "$url" ]; then
    sed -i "s#http://localhost:500${n}#${url}#g" /usr/share/nginx/html/*.html
  fi
done
