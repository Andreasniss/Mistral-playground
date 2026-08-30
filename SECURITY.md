# Security model

This repository is a learning reference, not a production service.

- Secrets are loaded from environment variables and excluded from version control.
- Tool execution is restricted to an explicit allow-list, JSON schemas reject extra
  fields, decoded arguments must be objects, and model/tool rounds are bounded.
- Logs and OpenTelemetry spans contain operational metadata, not prompt, response,
  tool-argument, or tool-result content.
- Telemetry export is disabled by default.
- The FastAPI surface binds to localhost and protects model endpoints with `X-API-Key`.
- Only transient `429` and `5xx` errors are retried; authentication and validation
  failures fail immediately.

Before production use, add identity-aware authorization, rate limiting, egress
controls, a secrets manager, content safety controls, dependency scanning, and a
formal threat model for each connected tool.

Please report vulnerabilities privately to the repository owner rather than opening
a public issue with exploit details.
