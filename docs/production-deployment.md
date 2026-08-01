# Production deployment

## What the repository now provides

- Reproducible, non-root backend and frontend container builds.
- A read-only Nginx edge container with request-size, connection, general API,
  and expensive-operation rate limits.
- CI tests, linting, dependency auditing, Bandit, CodeQL, and container builds.
- SemVer tag releases to GHCR for amd64/arm64 with SBOM, BuildKit provenance,
  and GitHub artifact attestations.
- Production configuration validation, narrow CORS, trusted-host enforcement,
  response hardening, bounded input fields, and bounded pagination.

## Required launch work

The current application has a hard-coded development user. Therefore it must
not be exposed to untrusted users yet. Select an OIDC/OAuth provider, validate
short-lived access tokens server-side (issuer, audience, signature, expiry),
and filter every run/report/event query by the authenticated subject. Prefer an
HttpOnly, Secure, SameSite session cookie via a same-origin backend-for-frontend
over storing bearer tokens in browser storage.

The job runner and live event bus are also process-local. Keep exactly one
backend replica until they are replaced by a durable queue plus shared pub/sub
(for example managed Redis with a separate worker deployment). After that,
make job claims idempotent, add retry/dead-letter policies, and autoscale API
and workers independently. A cloud load balancer/CDN should terminate TLS and
apply shared WAF/bot/rate policies; the included Nginx is the origin edge, not
a replacement for a distributed traffic service.

## Release

1. Protect `main` and require CI/CodeQL checks and review.
2. Enable GitHub secret scanning, push protection, Dependabot, and private
   vulnerability reporting.
3. Merge a reviewed version change and create a signed SemVer tag such as
   `v0.2.0`.
4. The release workflow publishes:
   `ghcr.io/OWNER/REPOSITORY-backend:0.2.0` and
   `ghcr.io/OWNER/REPOSITORY-frontend:0.2.0`.
5. Verify an image with
   `gh attestation verify oci://ghcr.io/OWNER/REPOSITORY-backend:0.2.0 -R OWNER/REPOSITORY`.

Copy `.env.example` to `.env`, replace every placeholder through a secret
manager, run Alembic migrations as a one-off release job using the direct
database URL, and then start the origin with `docker compose up --build -d`.
TLS is expected at the platform load balancer in front of port 8080.

Never run migrations concurrently in every API replica. Back up the database,
test restore procedures, set Gemini spending alerts/quotas, redact user input
from logs, and alert on 401/403/429/5xx rates, queue age, job duration, and cost.
