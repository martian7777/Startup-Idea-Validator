# Security policy

## Reporting a vulnerability

Do not open a public issue. Use GitHub's **Security → Report a vulnerability**
private reporting flow. Include the affected version, reproduction steps, and
impact. Maintainers should acknowledge reports within three business days.

## Deployment gates

This repository is not ready for anonymous public traffic. Before launch:

1. Put an identity-aware gateway in front of `/api/*`, validate identity at the
   API, and replace `dev_user_id` with the authenticated subject. Every query
   must filter by that subject. The current development identity is not tenant
   isolation.
2. Move jobs and event fan-out from process memory to a durable queue/pub-sub
   system before running more than one backend replica. The current API worker
   is deliberately single-replica.
3. Terminate TLS at the platform load balancer/CDN, enable WAF/bot controls,
   keep the backend network-private, and configure billing/spend alerts for the
   Gemini account.
4. Store secrets in the deployment platform's secret manager. Never bake `.env`
   files or credentials into images.
5. Enable GitHub branch protection, secret scanning/push protection, Dependabot
   alerts, code scanning, and required CI checks.

The included Nginx configuration provides an edge proxy, request-size limits,
connection limits, strict response headers, and a tighter rate limit on costly
run creation. In a multi-edge deployment, enforce rate limits in a shared
gateway/Redis service as well.
