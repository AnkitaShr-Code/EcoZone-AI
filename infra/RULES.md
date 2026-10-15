# infra/ rules

Build and deploy for the one Cloud Run service. Everything in [../docs/ENGINEERING_RULES.md](../docs/ENGINEERING_RULES.md) applies.

## Layout

```
infra/
  Dockerfile           stage 1: node builds app/dist; stage 2: python:3.12-slim + uv sync --frozen --no-dev, copies app/dist
  cloudbuild.yaml      build, push to Artifact Registry, deploy to Cloud Run
  setup.md             one-time project setup commands (APIs, buckets, service accounts, WIF), kept runnable
  iam.md               roles per service account and why
```

## Rules

- **One image, one service** (`ecozone`, region `asia-south1`). The image contains the app build and the Python packages, not the area bundle; the bundle is read from GCS at startup.
- **Service account** `ecozone-run@` has only Storage Object Viewer on the bundle bucket, Firestore User, BigQuery Data Editor on `ecozone_*` plus Job User, and Vertex AI User. A separate `ecozone-pipeline@` writes bundles and BigQuery tables. CI deploys as `ecozone-deploy@` through Workload Identity Federation.
- **No keys.** No service-account JSON keys are ever created. Local work uses `gcloud auth application-default login`.
- **Cloud Run settings** are in `cloudbuild.yaml`, not clicked in the console: memory sized for the bundle, concurrency, session affinity on, request timeout long enough for SSE (3600 s), min instances 0 except during judging (1).
- **Cost guard**: a billing budget alert on the project; search capped by round and time limits in `agents` settings.
- Every manual console change is written back into `setup.md` the same day.
