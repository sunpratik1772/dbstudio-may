# syntax=docker/dockerfile:1.6
#
# dbSherpa frontend container.
#
# Two stages so the runtime image carries only the static bundle plus
# nginx — no node_modules, no toolchain.
#
# Stage 1 (builder): install deps + `vite build` → /app/dist
# Stage 2 (runtime): nginx:alpine serving /app/dist on $PORT, with
#                    /api/* reverse-proxied to the backend URL provided
#                    at deploy time via the BACKEND_URL env var.
#
# Why reverse-proxy instead of baking the backend URL into JS at
# build time?
#   * Same image can promote dev → staging → prod by changing one env.
#   * Browser calls stay same-origin → no CORS, no preflight, SSE just
#     works.
#   * Rotating the backend URL doesn't require a frontend rebuild.
#
# Build locally:
#   docker build -t dbsherpa-frontend -f frontend/Dockerfile frontend
#
# Run locally (pointed at a local backend):
#   docker run --rm -p 8080:8080 \
#       -e BACKEND_URL=http://host.docker.internal:8000 \
#       dbsherpa-frontend
#
FROM node:20-alpine AS builder

WORKDIR /app

# Cache deps across code changes — copying only the manifests first
# means a TSX edit doesn't reinstall node_modules.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . ./
RUN npm run build


FROM nginx:1.27-alpine AS runtime

ENV PORT=8080 \
    BACKEND_URL=http://localhost:8000

# gettext ships `envsubst`, which we use at container start to render
# the nginx config with the actual BACKEND_URL. No other runtime deps.
RUN apk add --no-cache gettext \
    && rm /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# nginx:alpine already has an 'nginx' user; we drop into it at runtime
# by letting the master process manage workers as that user.
EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
