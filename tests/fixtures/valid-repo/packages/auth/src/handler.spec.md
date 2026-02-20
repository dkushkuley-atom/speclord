---
specVersion: "0.1.0"
inherits: "../.spec.yaml"
type: "api-endpoint"
status: "active"
owner: "@auth-team"
priority: "high"
dependencies: []
generates: "packages/auth/src/handler.py"
---

## Purpose

Handles authentication requests including login, logout, and session validation.

## Interface

- `POST /auth/login` — Authenticate user with credentials
- `POST /auth/logout` — Invalidate session
- `GET /auth/session` — Validate current session

## Behavior

1. Validate input credentials format
2. Check against user store
3. Return JWT on success

## Edge Cases

- Expired sessions return 401
- Invalid credentials return 403
- Rate limit after 5 failed attempts

## Testing Requirements

- Unit tests for each endpoint
- Integration test for full login flow
