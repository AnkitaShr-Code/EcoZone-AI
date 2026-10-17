# One-time project setup — EcoZone AI

Run these commands **once** to configure `ecozone-ai-2026` for Cloud Run deployment.
All manual console changes must be written back here the same day (infra/RULES.md).

No API keys are created at any step. Local auth: `gcloud auth application-default login`.
Service auth: Application Default Credentials via the service account on Cloud Run.

---

## Variables (set these in your shell first)

```bash
export PROJECT=ecozone-ai-2026
export REGION=asia-south1
export BILLING=<YOUR_BILLING_ACCOUNT_ID>   # gcloud billing accounts list
export SA_RUN=ecozone-run
export SA_PIPELINE=ecozone-pipeline
export SA_DEPLOY=ecozone-deploy
export REPO=ecozone-images
export BUNDLE_BUCKET=ecozone-bundles-ai2026
```

---

## 1. Project and billing (DONE Oct 16)

```bash
gcloud projects create $PROJECT --name="EcoZone AI"
gcloud billing projects link $PROJECT --billing-account=$BILLING
```

## 2. Enable APIs (DONE Oct 16)

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=$PROJECT
```

## 3. Artifact Registry

```bash
gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="EcoZone AI container images" \
  --project=$PROJECT

# Allow local docker pushes during development
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

## 4. Cloud Storage — area bundle bucket

```bash
gcloud storage buckets create gs://$BUNDLE_BUCKET \
  --project=$PROJECT \
  --location=$REGION \
  --uniform-bucket-level-access

# Versioning keeps old bundles safe
gcloud storage buckets update gs://$BUNDLE_BUCKET --versioning
```

## 5. Firestore database

```bash
# Native mode, same region
gcloud firestore databases create \
  --project=$PROJECT \
  --location=$REGION \
  --type=firestore-native
```

## 6. BigQuery dataset (analytics, runs, evals)

```bash
bq --project_id=$PROJECT mk \
  --dataset \
  --location=$REGION \
  --description="EcoZone AI analytics" \
  ecozone_deccan
```

## 7. Service accounts

### 7a. Cloud Run runtime SA

```bash
gcloud iam service-accounts create $SA_RUN \
  --display-name="EcoZone Cloud Run service" \
  --project=$PROJECT

# Storage: read bundles
gcloud storage buckets add-iam-policy-binding gs://$BUNDLE_BUCKET \
  --member="serviceAccount:${SA_RUN}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/storage.objectViewer

# Firestore: read/write sessions and plans
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_RUN}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/datastore.user

# BigQuery: write runs and eval results
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_RUN}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/bigquery.dataEditor

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_RUN}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/bigquery.jobUser

# Vertex AI: call Gemini
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_RUN}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/aiplatform.user
```

### 7b. Pipeline SA (writes bundles to GCS and BigQuery)

```bash
gcloud iam service-accounts create $SA_PIPELINE \
  --display-name="EcoZone pipeline (writes bundles)" \
  --project=$PROJECT

gcloud storage buckets add-iam-policy-binding gs://$BUNDLE_BUCKET \
  --member="serviceAccount:${SA_PIPELINE}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/storage.objectAdmin

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_PIPELINE}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/bigquery.dataEditor

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_PIPELINE}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/bigquery.jobUser
```

### 7c. Cloud Build / deploy SA

```bash
gcloud iam service-accounts create $SA_DEPLOY \
  --display-name="EcoZone CI deploy" \
  --project=$PROJECT

# Allow Cloud Build to deploy to Cloud Run
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_DEPLOY}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/run.admin

# Allow Cloud Build to push images
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_DEPLOY}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/artifactregistry.writer

# Allow Cloud Build SA to act as the run SA
gcloud iam service-accounts add-iam-policy-binding \
  ${SA_RUN}@${PROJECT}.iam.gserviceaccount.com \
  --member="serviceAccount:${SA_DEPLOY}@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/iam.serviceAccountUser \
  --project=$PROJECT
```

## 8. Cloud Build trigger (GitHub)

```bash
# First connect the GitHub repo via the console:
# Cloud Build > Triggers > Connect repository > GitHub > ecozone-ai repo
# (only needed once per repo; reuse the connection for any number of triggers)

# Verify Vertex AI model IDs first (step 11 below), then fill in the values below.
export MODEL_PROPOSER=<flash-model-id>   # e.g. gemini-2.0-flash-001
export MODEL_WRITER=<pro-model-id>       # e.g. gemini-2.5-pro-001
export GEMINI_LOC=$REGION               # location serving those models, e.g. asia-south1

# Then create the trigger:
# _REGION, _SERVICE, _REGISTRY, _REPO, _STORE all have defaults in cloudbuild.yaml — no need to pass them.
# $PROJECT_ID and $SHORT_SHA are Cloud Build built-ins; do NOT pass them as _PROJECT / _SHORT_SHA.
gcloud builds triggers create github \
  --name=deploy-main \
  --project=$PROJECT \
  --region=$REGION \
  --repo-name=EcoZone-AI \
  --repo-owner=<YOUR_GITHUB_USERNAME> \
  --branch-pattern=^main$ \
  --build-config=infra/cloudbuild.yaml \
  --service-account="projects/${PROJECT}/serviceAccounts/${SA_DEPLOY}@${PROJECT}.iam.gserviceaccount.com" \
  --substitutions=_BUNDLE_URI=gs://${BUNDLE_BUCKET}/areas,_GEMINI_LOC=${GEMINI_LOC},_MODEL_PROPOSER=${MODEL_PROPOSER},_MODEL_WRITER=${MODEL_WRITER}
```

> **Why not pass `_PROJECT` or `_SHORT_SHA`?** The new `cloudbuild.yaml` uses the Cloud Build built-ins
> `$PROJECT_ID` and `$SHORT_SHA` directly. Passing them as user-defined substitutions causes Cloud Build
> to warn about unused variables and is confusing. All credentials and config flow from Cloud at build
> time — no local values are baked in.

## 9. First manual deploy (before CI is wired)

Build and deploy locally — no GitHub push needed:

```bash
# Build the image
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/ecozone:init"
docker build -f infra/Dockerfile -t $IMAGE .

# Push
docker push $IMAGE

# Deploy
gcloud run deploy ecozone \
  --image=$IMAGE \
  --region=$REGION \
  --project=$PROJECT \
  --platform=managed \
  --service-account=${SA_RUN}@${PROJECT}.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=4 \
  --memory=2Gi \
  --cpu=2 \
  --concurrency=80 \
  --timeout=3600 \
  --session-affinity \
  --set-env-vars="ECOZONE_STORE=memory,GOOGLE_CLOUD_PROJECT=${PROJECT},ECOZONE_BUNDLE_URI="
```

The service URL printed at the end is the **live hackathon link**.

## 10. Billing budget alert

```bash
# Alert at 80% of $50 spend (adjust the amount to your credit balance)
gcloud billing budgets create \
  --billing-account=$BILLING \
  --display-name="EcoZone AI budget" \
  --budget-amount=50USD \
  --threshold-rule=percent=0.8
```

## 11. Vertex AI — verify model IDs

```bash
gcloud ai models list \
  --region=$REGION \
  --project=$PROJECT \
  --filter="displayName~gemini"
```

Record the exact model IDs and update `cloudbuild.yaml` substitutions and `.env`:
- `_MODEL_PROPOSER`: Flash tier (for search loop)
- `_MODEL_WRITER`: Pro tier (for explanations and briefs)

## 12. Upload bundle to GCS (after WP4 is done)

```bash
# Pipeline writes the bundle to data/areas/deccan/v1/ (uv run pipeline all --area deccan)
gcloud storage cp -r data/areas/deccan/v1/* gs://$BUNDLE_BUCKET/areas/deccan/v1/

# Re-deploy with the bundle URI set
gcloud run services update ecozone \
  --region=$REGION \
  --project=$PROJECT \
  --update-env-vars="ECOZONE_BUNDLE_URI=gs://${BUNDLE_BUCKET}/areas"
```

---

## Status log

| Date | Step | Done by |
|---|---|---|
| Oct 16 | Steps 1, 2 | Claude (automated) |
| Oct 16 | Steps 3–8 | Abhishek (WP3) |
| Oct 16–17 | Step 9 first deploy | Abhishek |
| Oct 17 | Step 12 bundle upload | Dhananjay + Abhishek |
| Oct 17 | Step 11 Vertex model IDs | Abhishek |
