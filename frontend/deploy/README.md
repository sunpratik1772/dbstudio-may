# Deploying the dbSherpa frontend to Cloud Run

The frontend is a Vite SPA. At runtime it's an nginx container that:

1. Serves the built bundle from `/usr/share/nginx/html`.
2. Reverse-proxies `/api/*` to the backend Cloud Run URL (set via the
   `BACKEND_URL` env var at deploy time).

This split is intentional:

* The SPA keeps calling `/api/...` exactly like it does in `vite dev`.
* The browser never sees the backend domain → no CORS, no preflight,
  SSE (for `/run/stream` and `/copilot/generate/stream`) just works.
* One image can be promoted across environments by changing a single
  env var — no rebuild.

## Architecture

```
┌────────────┐        ┌────────────────────┐        ┌──────────────────┐
│  Browser   │  HTTPS │  Cloud Run:         │  HTTPS │  Cloud Run:       │
│            │ ─────▶ │  dbsherpa-frontend  │ ─────▶ │  dbsherpa-backend │
│            │        │  (nginx + SPA)      │        │  (FastAPI)        │
└────────────┘        └────────────────────┘        └──────────────────┘
                        serves /           proxies /api/* → backend
                        SPA fallback       SSE-friendly (no buffering)
```

## Prerequisites

Backend deployed first (see `backend/deploy/README.md`). Grab its URL:

```bash
export BACKEND_URL=$(gcloud run services describe dbsherpa-backend \
    --region=$REGION --format='value(status.url)')
```

The rest of the setup (Artifact Registry repo, Cloud Build perms)
is shared with the backend runbook.

## Deploy

```bash
cd frontend
gcloud builds submit \
    --config deploy/cloudbuild.yaml \
    --substitutions=_REGION=$REGION,_BACKEND_URL=$BACKEND_URL \
    --project=$PROJECT_ID \
    .
```

Output prints the frontend URL. Visit it in a browser — the SPA loads,
talks to `/api/*` on its own origin, and the nginx proxy forwards to
the backend.

## Updating

* **Code change** — re-run `gcloud builds submit` as above. New image,
  new revision.
* **Backend URL change** — re-deploy with the new `_BACKEND_URL`
  substitution; the image doesn't need to be rebuilt (Cloud Build will
  skip to the deploy step if the content is identical).

## Local parity

Verify the container before pushing:

```bash
# 1. Have the backend running locally (port 8000)
cd ../backend && uvicorn app.main:app --port 8000 &

# 2. Build & run the frontend image, pointed at host-gateway backend
cd ../frontend
docker build -t dbsherpa-frontend -f Dockerfile .
docker run --rm -p 8080:8080 \
    -e BACKEND_URL=http://host.docker.internal:8000 \
    dbsherpa-frontend

# Open http://localhost:8080
```

## SSE sanity

The nginx config turns off `proxy_buffering` and extends timeouts to
600s specifically so workflow execution streams (`/run/stream`) and
copilot generation streams (`/copilot/generate/stream`) don't stall.
If you see the UI get stuck partway through a run, this is the first
thing to check — `docker logs` on the frontend container will show
nginx errors about closed upstreams.

## Cost profile

nginx is cheap: 1 vCPU / 256 MiB with scale-to-zero. At rest the
frontend costs nothing; under a busy demo it usually sits on a single
warm instance. Bump `maxScale` in `service.yaml` if you need more.
