# infra/

Deployment and operations. Lane: **A**.

One Dockerfile builds the `app/` React build and copies it into the Python image alongside `api/`, `engine/`, and `agents/`, so one Cloud Run service serves everything with no proxy in front of it. Cloud Build or GitHub Actions deploys on push to `main`. Service account scoped to BigQuery Data Viewer/Job User, Firestore User, Storage Object Viewer, and Vertex AI User — no API keys anywhere.

Not yet implemented. Deployment detail: [../docs/DESIGN.md](../docs/DESIGN.md#c8-deployment-and-operations).
