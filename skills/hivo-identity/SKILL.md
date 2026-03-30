---
name: hivo-identity
description: Manage this agent's identity credentials for the Hivo ecosystem. Use this skill whenever the user asks to register the agent, generate or refresh an access token, check identity info, set up credentials, authenticate with hivo-identity, or call any service that requires a Bearer token.
---

# Hivo Identity

This skill manages the Ed25519 keypair and registration state that identify this agent within the Hivo ecosystem. It bundles three scripts:

| Script | Purpose |
|--------|---------|
| `scripts/register.py` | One-time setup: generate a keypair, register with hivo-identity, write credentials to `assets/` |
| `scripts/get_token.py` | Get a Bearer access token for a target service; handles caching, refresh, and fallback automatically |
| `scripts/me.py` | Show the agent's current identity info (sub, handle, status, etc.) from the identity service |

Files in `assets/`:

| File | Committed? | Description |
|------|-----------|-------------|
| `assets/config.json` | Yes | Deployment config: `issuer_url` (edit before registering) |
| `assets/private_key.pem` | **No — secret** | Ed25519 private key |
| `assets/public_key.jwk` | No | Corresponding public key (JWK), generated artifact |
| `assets/identity.json` | No | Registration result: `sub`, `handle`, `iss` |
| `assets/token_cache.json` | **No — secret** | Cached access tokens and refresh tokens, keyed by audience |

---

## Requirements

All scripts require Python 3.12+ and the `cryptography` package:

```bash
pip install cryptography
# or, if the project uses uv:
uv add cryptography
```

---

## Workflow

### First time: Configure and register

1. Edit `assets/config.json` to set `issuer_url` for your deployment (default: public cloud instance `https://id.hivo.ink`).

2. Run `register.py` with the desired handle:

```bash
python scripts/register.py <handle>
# or override the issuer: python scripts/register.py <handle> <issuer_url>
```

**Example:**
```bash
python scripts/register.py myagent@acme
```

This will:
1. Generate a fresh Ed25519 keypair
2. Register with the identity service (challenge-proof flow)
3. Write `assets/private_key.pem`, `assets/public_key.jwk`, `assets/identity.json`

All three output files are gitignored — per-deployment artifacts. Only `assets/config.json` is committed.

---

### Every time: Get a token

`audience` identifies the target service you want to call:

```bash
python scripts/get_token.py <audience>
```

Prints the `access_token` to stdout. Pass it as a Bearer token:

```bash
TOKEN=$(python scripts/get_token.py <audience>)
curl -H "Authorization: Bearer $TOKEN" <service_url>
```

**Token lifecycle and caching** — the script handles everything automatically:

| Step | Condition | Action |
|------|-----------|--------|
| 1 | Cached access token still valid (>60s remaining) | Return it immediately |
| 2 | Access token expired; refresh token still valid (up to 30 days) | Call `POST /token/refresh`, update cache |
| 3 | Refresh token expired or missing | Call `POST /token` with a fresh private_key_jwt assertion, update cache |

Tokens are stored in `assets/token_cache.json` (gitignored). Each entry is keyed by audience, so tokens for different services are tracked independently.

---

### Check identity: /me

```bash
python scripts/me.py
```

Calls `GET /me` on the identity service and prints:

```
sub:          agt_01jz...
handle:       myagent@acme
status:       active
created_at:   2025-...
```

Also shows `display_name` and `email` if set.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `assets/identity.json not found` | Registration not done | Run `register.py` first |
| `assets/private_key.pem not found` | Key file missing | Re-register with `register.py` (old `sub` will be orphaned) |
| `Error 400: invalid_assertion` | Clock skew or corrupted key | Check system time; if key is corrupt, re-register |
| `Error 401: invalid_token` (on /me or refresh) | Token expired or invalid | Run `get_token.py` to get a fresh token via assertion flow |
| `Error 409: handle_taken` | Handle already registered | Choose a different handle, or reuse existing `identity.json` + `private_key.pem` |
| `Error 422: validation_error` | Bad handle format | Handle must be `name@namespace`, each part 2–32 chars, letters/digits/hyphens only |

---

## When helping the user

- **If no `assets/identity.json` exists**: registration is required. Ask for a handle and confirm the issuer URL (default: `https://id.hivo.ink`), then run `register.py`.
- **If `assets/identity.json` exists**: read it to show the user their `sub` and `handle` before doing anything else.
- **Getting a token**: always run `get_token.py <audience>` and capture stdout. Ask the user which service they are calling to determine the audience.
- **Using the token**: pass it as `Authorization: Bearer <token>` to any Hivo service.
- **Checking identity info**: run `me.py` — do not ask the user to call the API manually. Run the script and show them the output.
- **Token freshness**: you do not need to track token expiry yourself — `get_token.py` handles caching and refresh automatically. Just call it before each service request.
- After registration, clarify that `private_key.pem`, `public_key.jwk`, `identity.json`, and `token_cache.json` are all gitignored. Only `assets/config.json` is committed.
