# Workflow Configuration Guide

## Overview

These workflows handle CI, Docker builds, AWS deployments, release tagging, and PR notifications for m8flow.

## Workflows

### `ci.yml`

**Purpose:** Runs linting, type checks, and tests on pull requests and pushes to `main`.

**Triggers:** Push or PR to `main`, manual dispatch.

**Jobs (path-filtered):**
- **extensions-backend** — Ruff lint, MyPy type check, Pytest for `extensions/m8flow-backend/`
- **extensions-frontend** — Lint, typecheck, and tests for `extensions/m8flow-frontend/`
- **codeql** — CodeQL security scan (Python + JS) on PRs
- **trivy** — Filesystem vulnerability scan (CRITICAL/HIGH) on PRs
- **migration-check** — Calls `check-migrations.yml` when migration files change on PRs
- **docker-dry-run** — Builds all Docker images without pushing on PRs

---

### `check-migrations.yml`

**Purpose:** Reusable workflow (called by `ci.yml`) that validates migration files in PRs.

**Triggers:** `workflow_call` only.

**What it checks:**
1. PR description contains a `Migration Plan` section with `Backward Compatibility`, `Rollback`, and `Expand/Contract` entries
2. No destructive operations (`DROP TABLE`, `DROP COLUMN`, etc.) without explicit `Destructive Migration Approved` in the PR body
3. All Alembic revision files in `extensions/m8flow-backend/migrations/versions/` are valid Python

---

### `create-release-tag.yml`

**Purpose:** Creates an annotated RC release tag on a commit from `main`.

**Triggers:** Manual (`workflow_dispatch`).

**Inputs:**
- `commit_sha` — SHA to tag (defaults to latest on `main`)
- `tag_name` — Tag in `X.Y.Z-rc` format (auto-increments patch if omitted)

**Required permissions:** `contents: write` on the repo (enforced at runtime via collaborator check).

---

### `deploy-docker.yml`

**Purpose:** Builds and pushes all four Docker images to Docker Hub.

**Triggers:**
- Manual (`workflow_dispatch`) with an `rc_tag` input
- Automatically after `create-release-tag.yml` completes successfully on `main` (when `AUTO_BUILD` variable is `true`)

**Images built:** `m8flow-backend`, `m8flow-frontend`, `m8flow-keycloak`, `m8flow-connector-proxy`

---

### `deploy-aws.yml`

**Purpose:** Deploys **seven** ECS services to AWS for GitHub Environments **DEV** or **QA**: backend, frontend, keycloak, connector-proxy, Celery worker, Celery Flower, and NATS consumer. Each run renders a new task definition revision with the requested image tag and deploys it with `force-new-deployment`. Cluster, service, and task-definition family names come from **environment secrets** (set them to match your Terraform outputs, e.g. in **m8flow-deployment** `terraform/aws/ecs.tf`).

**Triggers:** Manual (`workflow_dispatch`).

**Repository variable (all environments):**
- `AWS_REGION` — e.g. `us-east-2`

**Environment secrets (per `DEV` / `QA`):**
- `AWS_ROLE_ARN` — IAM role ARN for OIDC (`configure-aws-credentials`)
- `ECS_CLUSTER` — ECS cluster name
- Per service (task definition family, ECS service name, and container name for render):
  - `BACKEND_TASK_DEF_FAMILY`, `BACKEND_SERVICE_NAME`, `BACKEND_CONTAINER_NAME`
  - `FRONTEND_TASK_DEF_FAMILY`, `FRONTEND_SERVICE_NAME`, `FRONTEND_CONTAINER_NAME`
  - `KEYCLOAK_TASK_DEF_FAMILY`, `KEYCLOAK_SERVICE_NAME`, `KEYCLOAK_CONTAINER_NAME`
  - `CONNECTOR_PROXY_TASK_DEF_FAMILY`, `CONNECTOR_PROXY_SERVICE_NAME`, `CONNECTOR_PROXY_CONTAINER_NAME`
- Backend-image services (task family and service only; container names are fixed in the workflow: `celery_worker`, `celery_flower`, `nats-consumer`):
  - `CELERY_WORKER_TASK_DEF_FAMILY`, `CELERY_WORKER_SERVICE_NAME`
  - `CELERY_FLOWER_TASK_DEF_FAMILY`, `CELERY_FLOWER_SERVICE_NAME`
  - `NATS_CONSUMER_TASK_DEF_FAMILY`, `NATS_CONSUMER_SERVICE_NAME`

**Images:** `m8flow-backend`, `m8flow-frontend`, `m8flow-keycloak`, and `m8flow-connector-proxy` on Docker Hub (`docker.io/m8flow/m8flow-<component>:<image_tag>`). Celery worker, Celery Flower, and NATS consumer use the **same backend image** as the main backend service.

**Inputs:**
- `environment` — `DEV` or `QA` (selects the GitHub Environment and its secrets)
- `image_tag` — tag to deploy (must exist on Docker Hub for the four verified repos)

**Operational note:** Phased Terraform rollout and service naming examples for QA are described in `m8flow-deployment/terraform/aws/docs/aws_deployment.md`.

---

### `pr-notification.yml`

**Purpose:** Sends a Google Chat notification when a non-draft PR targeting `main` is opened.

**Triggers:** `pull_request_target` opened on `main`.


