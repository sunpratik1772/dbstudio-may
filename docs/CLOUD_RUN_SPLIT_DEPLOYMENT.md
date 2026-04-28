# Cloud Run Split Deployment

> Goal: deploy dbSherpa as two independent Cloud Run services:
> one FastAPI backend endpoint and one React/nginx frontend endpoint.
> The frontend serves the UI and reverse-proxies `/api/*` to the backend.

## Target Shape

```text
Browser
  |
  | https://dbsherpa-frontend-...run.app
  v
Cloud Run: dbsherpa-frontend
  - nginx
  - static Vite bundle
  - proxies /api/* to BACKEND_URL
  |
  | https://dbsherpa-backend-...run.app
  v
Cloud Run: dbsherpa-backend
  - FastAPI
  - workflow engine
  - Copilot / LLM integration
  - report generation
```

The browser should normally call only the frontend origin:

```text
GET /api/node-manifest
POST /api/validate
POST /api/run/stream
POST /api/copilot/generate/stream
```

The frontend nginx container strips `/api` and forwards to the backend, so the
backend still receives its normal routes:

```text
GET /node-manifest
POST /validate
POST /run/stream
POST /copilot/generate/stream
```

This avoids CORS and keeps Server-Sent Events stable.

## Repo Split

The current monorepo already has clean deploy boundaries:

```text
dbsherpa/
  backend/
    Dockerfile
    deploy/
      cloudbuild.yaml
      service.yaml
    app/
    engine/
    data_sources/
    skills/
    workflows/

  frontend/
    Dockerfile
    deploy/
      cloudbuild.yaml
      service.yaml
    nginx/
    src/

  docs/
  README.md
  start.sh
```

For Cloud Run, treat `backend/` and `frontend/` as separate build contexts.
Do not build from the repo root.

Backend build context:

```bash
cd backend
gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=$REGION \
  --project=$PROJECT_ID \
  .
```

Frontend build context:

```bash
cd frontend
gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_BACKEND_URL=$BACKEND_URL \
  --project=$PROJECT_ID \
  .
```

## What Belongs Where

Backend-owned:

- FastAPI routes: `backend/app/`
- workflow runner and validator: `backend/engine/`
- node definitions: `backend/engine/nodes/*.yaml` and `*.py`
- data-source metadata: `backend/data_sources/metadata/*.yaml`
- Copilot skills: `backend/skills/*.md`
- saved workflows/templates: `backend/workflows/`, `backend/templates/`
- Python dependencies: `backend/requirements.txt`
- backend image/deploy config: `backend/Dockerfile`, `backend/deploy/`

Frontend-owned:

- React app: `frontend/src/`
- generated/fallback node metadata: `frontend/src/nodes/generated.ts`
- API client: `frontend/src/services/api.ts`
- nginx reverse proxy: `frontend/nginx/`
- Node dependencies: `frontend/package.json`, `frontend/package-lock.json`
- frontend image/deploy config: `frontend/Dockerfile`, `frontend/deploy/`

Shared, but not deployed as an app:

- `docs/`
- root `README.md`
- root `node_detail.md`
- `start.sh` local developer launcher

## First-Time GCP Setup

Set project variables:

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
gcloud config set project "$PROJECT_ID"
```

Enable required APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  --project "$PROJECT_ID"
```

Create one Artifact Registry repo for both images:

```bash
gcloud artifacts repositories create dbsherpa \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID"
```

Create a runtime service account for the backend:

```bash
gcloud iam service-accounts create dbsherpa-backend \
  --display-name="dbSherpa backend runtime" \
  --project="$PROJECT_ID"
```

Store the Gemini key in Secret Manager:

```bash
echo -n "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
  --data-file=- \
  --project="$PROJECT_ID"
```

Allow the backend runtime service account to read it:

```bash
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:dbsherpa-backend@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor \
  --project="$PROJECT_ID"
```

Allow Cloud Build to deploy Cloud Run services:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role=roles/run.admin

gcloud iam service-accounts add-iam-policy-binding \
  "dbsherpa-backend@$PROJECT_ID.iam.gserviceaccount.com" \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role=roles/iam.serviceAccountUser \
  --project="$PROJECT_ID"
```

## Deploy Order

Deploy backend first:

```bash
cd backend
gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions=_REGION="$REGION" \
  --project="$PROJECT_ID" \
  .
cd ..
```

Capture the backend endpoint:

```bash
export BACKEND_URL=$(gcloud run services describe dbsherpa-backend \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')

echo "$BACKEND_URL"
```

Smoke test backend directly:

```bash
curl -fsS "$BACKEND_URL/"
curl -fsS "$BACKEND_URL/node-manifest" | python3 -m json.tool >/dev/null
```

Deploy frontend with the backend URL:

```bash
cd frontend
gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_BACKEND_URL="$BACKEND_URL" \
  --project="$PROJECT_ID" \
  .
cd ..
```

Capture the frontend endpoint:

```bash
export FRONTEND_URL=$(gcloud run services describe dbsherpa-frontend \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')

echo "$FRONTEND_URL"
```

Smoke test through the frontend proxy:

```bash
curl -fsS "$FRONTEND_URL/healthz"
curl -fsS "$FRONTEND_URL/api/node-manifest" | python3 -m json.tool >/dev/null
```

Then open:

```text
$FRONTEND_URL
```

## Endpoint Wiring

The frontend TypeScript client intentionally uses relative `/api` URLs:

```text
frontend/src/services/api.ts
frontend/src/store/nodeRegistryStore.ts
```

In local Vite dev, `frontend/vite.config.ts` proxies `/api` to
`http://localhost:8000`.

In Cloud Run, nginx proxies `/api/*` to the `BACKEND_URL` env var:

```text
frontend/nginx/default.conf.template
frontend/nginx/entrypoint.sh
frontend/deploy/service.yaml
```

Do not hard-code the backend Cloud Run URL into React code. Keep it as a
frontend service env var so the same frontend image can move across dev,
staging, and prod.

## Service Configuration

Backend Cloud Run service:

- service name: `dbsherpa-backend`
- image: Artifact Registry `backend:<sha>`
- port: `$PORT` / `8080`
- required secret/env: `GEMINI_API_KEY`
- writable paths:
  - `DBSHERPA_WORKFLOWS_DIR=/tmp/dbsherpa/workflows`
  - `DBSHERPA_DRAFTS_DIR=/tmp/dbsherpa/drafts`
  - `DBSHERPA_OUTPUT_DIR=/tmp/dbsherpa/output`

Frontend Cloud Run service:

- service name: `dbsherpa-frontend`
- image: Artifact Registry `frontend:<sha>`
- port: `$PORT` / `8080`
- required env:
  - `BACKEND_URL=https://dbsherpa-backend-...run.app`

## Persistence Caveat

Cloud Run instance filesystem is ephemeral. The backend currently writes saved
workflows, drafts, and reports to `/tmp/dbsherpa/...` in the container.

That is fine for demos and review environments, especially with low scale.
For production persistence:

1. Mount a GCS bucket with Cloud Run volume mounts / GCS FUSE.
2. Point these env vars at the mount:

```text
DBSHERPA_WORKFLOWS_DIR=/mnt/dbsherpa/workflows
DBSHERPA_DRAFTS_DIR=/mnt/dbsherpa/drafts
DBSHERPA_OUTPUT_DIR=/mnt/dbsherpa/output
```

No workflow engine code should need to change.

## If You Split Into Two Git Repos Later

The clean split is:

```text
dbsherpa-backend-repo/
  backend contents moved to repo root
  deploy/
  Dockerfile
  requirements.txt

dbsherpa-frontend-repo/
  frontend contents moved to repo root
  deploy/
  Dockerfile
  nginx/
  package.json
  src/
```

If you do that, update:

- Cloud Build commands so the build context is each repo root.
- Dockerfile `COPY` paths if files moved.
- GitHub Actions or Cloud Build triggers to watch each repo separately.
- Docs links that currently point to `backend/...` or `frontend/...`.

Keep generated artifacts in sync:

- backend still owns the source NodeSpecs.
- frontend still needs `frontend/src/nodes/generated.ts` as a fallback.
- after NodeSpec changes, run `uv run python backend/scripts/gen_artifacts.py`
  before pushing both backend and frontend repos.

For now, keeping the monorepo is simpler because one commit can update:

- backend NodeSpec,
- generated frontend fallback metadata,
- docs,
- tests.

## Pre-Push Checklist

Run from repo root:

```bash
uv run pytest backend/tests -q
npm --prefix frontend run build
```

Then check deploy configs:

```bash
gcloud builds submit --config backend/deploy/cloudbuild.yaml backend
gcloud builds submit --config frontend/deploy/cloudbuild.yaml frontend
```

Before making the services public, decide whether the environment should use:

- public `allUsers` Cloud Run invoker for demos, or
- IAP / authenticated invoker for internal production.

