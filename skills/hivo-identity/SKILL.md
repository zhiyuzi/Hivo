---
name: agent-identity-credential
description: Manage this agent's identity credentials for the agentinfra ecosystem. Use this skill whenever the user asks to register the agent, generate or refresh an access token, set up credentials, authenticate with agent-identity, or call any service that requires a Bearer token. Also use when the user wants to check their agent's identity or troubleshoot authentication.
---

# Agent Identity Credential

This skill manages the Ed25519 keypair and registration state that identify this agent within the agentinfra ecosystem. It bundles two scripts:

| Script | Purpose |
|--------|---------|
| `scripts/register.py` | One-time setup: generate a keypair, register with agent-identity, write credentials to `assets/` |
| `scripts/get_token.py` | Ongoing: read saved credentials, exchange for an access token, print it to stdout |

Credentials live in `assets/`:

| File | Secret? | Description |
|------|---------|-------------|
| `assets/private_key.pem` | **YES — never commit** | Ed25519 private key |
| `assets/public_key.jwk` | No | Corresponding public key (JWK format) |
| `assets/identity.json` | No | Registration result: `sub`, `handle`, `iss` |

---

## Requirements

Both scripts require Python 3.12+ and the `cryptography` package:

```bash
pip install cryptography
```

Or, if the project uses uv:

```bash
uv add cryptography
```

---

## Workflow

### First time: Register

Run `register.py` with the desired handle and the identity service URL:

```bash
python scripts/register.py <handle> <issuer_url>
```

**Example:**
```bash
python scripts/register.py myagent@acme https://id.agentinfra.cloud
```

This will:
1. Generate a fresh Ed25519 keypair
2. Register with the identity service (challenge-proof flow)
3. Write `assets/private_key.pem`, `assets/public_key.jwk`, `assets/identity.json`

After registration, commit `public_key.jwk` and `identity.json`. Never commit `private_key.pem` — it is listed in `assets/.gitignore`.

### Every time: Get a token

```bash
python scripts/get_token.py
```

Prints the `access_token` to stdout. Use it as a Bearer token for downstream services:

```bash
TOKEN=$(python scripts/get_token.py)
curl -H "Authorization: Bearer $TOKEN" <service_url>
```

The access token is valid for 1 hour. Simply re-run `get_token.py` to get a fresh one — the script always fetches a new token from the identity service.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `assets/identity.json not found` | Registration not done | Run `register.py` first |
| `assets/private_key.pem not found` | Key file missing or deleted | Re-register with `register.py` (generates a new keypair; the old `sub` will be orphaned) |
| `Error 400: invalid_assertion` | Clock skew or corrupted key | Check system time; if key is corrupt, re-register |
| `Error 409: handle_taken` | Handle already registered | Choose a different handle, or use the existing `identity.json` and `private_key.pem` |
| `Error 422: validation_error` | Bad handle format | Handle must be `name@namespace`, each part 2–32 chars, letters/digits/hyphens only |

---

## When helping the user

- **If no `assets/identity.json` exists**: registration is required first. Ask for a handle and issuer URL (default: `https://id.agentinfra.cloud`), then run `register.py`.
- **If `assets/identity.json` exists**: read it to show the user their current `sub` and `handle` before doing anything else.
- **Getting a token**: always run `get_token.py` and capture stdout. Do not ask the user to run it manually unless they prefer that.
- **Using the token**: pass it as `Authorization: Bearer <token>` to any agentinfra service.
- After registration, remind the user to commit `public_key.jwk` and `identity.json` but **not** `private_key.pem`.
