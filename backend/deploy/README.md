# Deploying the dbSherpa backend to Cloud Run

Two files drive the deploy:

| File | Purpose |
|------|---------|
| `backend/Dockerfile` | Container image. Single-process uvicorn on `$PORT`, non-root user, writable state redirected to `/tmp`. |
| `deploy/service.yaml` | Declarative Cloud Run service spec — git-versioned, applied with `gcloud run services replace`. |
| `deploy/cloudbuild.yaml` | One-command CI pipeline: build → push → deploy → smoke. |

## First-time setup (per GCP project)

```bash
export PROJECT_ID=your-project
export REGION=us-central1

# 1. Enable APIs
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    --project $PROJECT_ID

# 2. Create Artifact Registry repo
gcloud artifacts repositories create dbsherpa \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID

# 3. Store the Gemini API key as a secret
echo -n "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
    --data-file=- --project=$PROJECT_ID

# 4. Runtime service account (least-privilege)
gcloud iam service-accounts create dbsherpa-backend \
    --display-name="dbSherpa backend runtime" \
    --project=$PROJECT_ID

gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:dbsherpa-backend@$PROJECT_ID.iam.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor \
    --project=$PROJECT_ID

# 5. Grant Cloud Build permission to deploy
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
    --role=roles/run.admin
gcloud iam service-accounts add-iam-policy-binding \
    dbsherpa-backend@$PROJECT_ID.iam.gserviceaccount.com \
    --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
    --role=roles/iam.serviceAccountUser \
    --project=$PROJECT_ID
```

## Deploy

```bash
cd backend
gcloud builds submit \
    --config deploy/cloudbuild.yaml \
    --substitutions=_REGION=$REGION \
    --project=$PROJECT_ID \
    .
```

The pipeline prints the final URL. The service is public by default
(`allUsers` → `roles/run.invoker`); remove that step in
`cloudbuild.yaml` for locked-down environments.

## Updating in place

Edit `deploy/service.yaml` (e.g. bump memory, change min-instances)
and reapply:

```bash
gcloud run services replace deploy/service.yaml \
    --region=$REGION --project=$PROJECT_ID
```

## State caveats

On Cloud Run the container filesystem is **read-only except for
`/tmp`**, and `/tmp` is **not shared across instances**. That means:

* Saved workflows, drafts, and generated reports live in `/tmp` on
  whichever instance handled the write. On scale-down / scale-up
  they're gone.
* This is fine for demo / review use with `maxScale: 1` or a single
  warm instance.
* For production persistence, mount a GCS bucket via
  [GCS FUSE](https://cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts)
  and point `DBSHERPA_WORKFLOWS_DIR` / `DBSHERPA_DRAFTS_DIR` /
  `DBSHERPA_OUTPUT_DIR` at the mount path. No code changes required.

## Local parity check

Before pushing, verify the container works end-to-end locally:

```bash
docker build -t dbsherpa-backend -f Dockerfile .
docker run --rm -p 8080:8080 \
    -e GEMINI_API_KEY=$GEMINI_API_KEY \
    dbsherpa-backend

# In another shell:
curl http://localhost:8080/
curl http://localhost:8080/contracts | jq '.nodes | keys'
curl http://localhost:8080/data_sources | jq '.sources[].id'
```
