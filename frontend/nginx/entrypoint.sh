#!/bin/sh
#
# Render the nginx config with runtime env vars and exec nginx.
#
# We pass an explicit allow-list to `envsubst` so nginx's own `$var`
# references pass through unmolested. Missing vars fall back to the
# defaults baked in the Dockerfile (PORT=8080, BACKEND_URL=localhost).
set -eu

: "${PORT:=8080}"
: "${BACKEND_URL:=http://localhost:8000}"

export PORT BACKEND_URL

envsubst '${PORT} ${BACKEND_URL}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "[entrypoint] PORT=$PORT BACKEND_URL=$BACKEND_URL"
nginx -t
exec nginx -g 'daemon off;'
