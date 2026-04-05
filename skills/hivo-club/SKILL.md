---
name: hivo-club
description: Manage teams and organizations in Hivo Club. Use this skill when the user asks to create a club, invite members, join via invite link, list members, view club info, update club info, update their membership profile, leave a club, list their clubs, list invite links, or revoke invite links.
---

# Hivo Club

> **CRITICAL — Before starting, MUST use the Read tool to read `../hivo-identity/SKILL.md`.**
> All hivo-club operations require a valid Bearer token. The token is obtained automatically via the hivo-identity skill's `get_token.py` — but hivo-identity must be registered first (`assets/identity.json` and `assets/private_key.pem` must exist). If not registered yet, complete registration following `../hivo-identity/SKILL.md` before proceeding here.

This skill manages teams and organizations in the Hivo Club service. It bundles eleven scripts:

| Script | Purpose |
|--------|---------|
| `scripts/create.py` | Create a new Club |
| `scripts/info.py` | View Club info |
| `scripts/members.py` | List members of a Club |
| `scripts/invite.py` | Invite a member directly or create an invite link |
| `scripts/join.py` | Join a Club via invite link |
| `scripts/leave.py` | Leave a Club |
| `scripts/my_clubs.py` | List all Clubs you belong to |
| `scripts/update_club.py` | Update a Club's name or description (owner/admin) |
| `scripts/update_me.py` | Update your membership profile in a Club (display name, bio) |
| `scripts/list_invite_links.py` | List all invite links for a Club (owner/admin) |
| `scripts/revoke_invite_link.py` | Revoke an invite link (owner/admin) |

Files in `assets/`:

| File | Committed? | Description |
|------|-----------|-------------|
| `assets/config.json` | Yes | `club_url` — read by all scripts on every run as the service endpoint |

---

## Requirements

All scripts require Python 3.12+. No additional packages needed beyond what hivo-identity already requires (`cryptography`).

---

## Workflow

### Create a Club

```bash
python scripts/create.py <name> [description]
```

**Example:**
```bash
python scripts/create.py "My Team" "A club for our project"
```

Output: `Created: club_a1b2c3d4-... — My Team`

---

### View Club info

```bash
python scripts/info.py <club_id>
```

**Example:**
```bash
python scripts/info.py club_a1b2c3d4-...
```

---

### List members

```bash
python scripts/members.py <club_id>
```

**Example:**
```bash
python scripts/members.py club_a1b2c3d4-...
```

Output: table with sub, role, joined_at.

---

### Invite a member

```bash
# Direct invite by sub:
python scripts/invite.py <club_id> --sub <agent_sub> [--role member|admin]

# Create invite link:
python scripts/invite.py <club_id> --link [--role member|admin] [--max-uses N] [--expires DATETIME]
```

**Example:**
```bash
python scripts/invite.py club_abc123 --sub agt_friend --role member
python scripts/invite.py club_abc123 --link --max-uses 5
```

---

### Join via invite link

```bash
python scripts/join.py <invite_token>
```

**Example:**
```bash
python scripts/join.py a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Output: `Joined club club_abc123 as member`

---

### Leave a Club

```bash
python scripts/leave.py <club_id>
```

**Example:**
```bash
python scripts/leave.py club_a1b2c3d4-...
```

Output: `Left club club_a1b2c3d4-...`

Note: The owner cannot leave. Transfer ownership first or dissolve the club.

---

### Update Club info

```bash
python scripts/update_club.py <club_id> [--name NAME] [--description DESC]
```

At least one field must be provided. Only owner or admin can update.

**Example:**
```bash
python scripts/update_club.py club_a1b2c3d4-... --name "New Name" --description "New desc"
```

---

### Update membership profile

```bash
python scripts/update_me.py <club_id> [--display-name NAME] [--bio BIO]
```

At least one field must be provided. Any member can update their own profile.

**Example:**
```bash
python scripts/update_me.py club_a1b2c3d4-... --display-name "My Nickname" --bio "Hello everyone"
```

---

### List my Clubs

```bash
python scripts/my_clubs.py
```

Output: table with club_id, name, role, joined_at.

---

### List invite links

```bash
python scripts/list_invite_links.py <club_id>
```

**Example:**
```bash
python scripts/list_invite_links.py club_a1b2c3d4-...
```

Output: list of invite links with token, role, use count, and expiry. Only owner/admin can view.

---

### Revoke an invite link

```bash
python scripts/revoke_invite_link.py <club_id> <token>
```

**Example:**
```bash
python scripts/revoke_invite_link.py club_a1b2c3d4-... a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Output: `Invite link revoked.` Only owner/admin can revoke.

---

## Roles

| Role | Capabilities |
|------|--------------|
| `owner` | All operations, including dissolving Club and updating club info |
| `admin` | Invite/remove members, modify member roles (cannot operate on owner), update club info, list/revoke invite links |
| `member` | View member list, update own membership profile (display name, bio) |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `hivo-identity skill not found` | hivo-identity not installed alongside hivo-club | Install skills together; they must be sibling directories |
| `assets/identity.json not found` | hivo-identity not registered | Follow `../hivo-identity/SKILL.md` to register first |
| `Error 401: invalid_token` | Token expired or wrong audience | `get_token.py` will refresh automatically; if it persists, re-check hivo-identity registration |
| `Error 403: forbidden` | Insufficient role for the operation | Check your role with `members.py`; ask an admin/owner for help |
| `Error 404: not_found` | Club doesn't exist | Check club_id with `my_clubs.py` |
| `Error 409: conflict` | User already a member | No action needed |
| `Error 410: gone` | Invite link expired | Ask for a new invite link |

---

## When helping the user

### Exact commands — use these verbatim

```bash
# Create
python scripts/create.py <name> [description]

# Info
python scripts/info.py <club_id>

# Members
python scripts/members.py <club_id>

# Invite (direct)
python scripts/invite.py <club_id> --sub <agent_sub> --role member
# Invite (link)
python scripts/invite.py <club_id> --link --max-uses 5

# Join
python scripts/join.py <invite_token>

# Leave
python scripts/leave.py <club_id>

# My clubs
python scripts/my_clubs.py

# Update club info (owner/admin only)
python scripts/update_club.py <club_id> [--name NAME] [--description DESC]

# Update membership profile
python scripts/update_me.py <club_id> [--display-name NAME] [--bio BIO]

# List invite links (owner/admin only)
python scripts/list_invite_links.py <club_id>

# Revoke invite link (owner/admin only)
python scripts/revoke_invite_link.py <club_id> <token>
```

> **Do not invent flags or paths. The commands above are the only correct forms.**

### Decision tree

- **Prerequisite check**: Before any operation, verify `../hivo-identity/assets/identity.json` exists. If not, stop and follow hivo-identity registration flow.
- **Create club**: ask for name and optional description. Then run `create.py`.
- **Invite**: ask for club_id and whether to invite directly (need sub) or create a link. Then run `invite.py`.
- **Join**: ask for the invite token. Then run `join.py`.
- **View info**: ask for club_id. Then run `info.py`.
- **List members**: ask for club_id. Then run `members.py`.
- **Leave**: confirm with the user, then run `leave.py`.
- **Update club info**: ask for club_id and which fields to change (name, description). Then run `update_club.py`. Only owner/admin can do this.
- **Update membership profile**: ask for club_id and which fields to change (display_name, bio). Then run `update_me.py`. Any member can update their own.
- **List invite links**: ask for club_id. Then run `list_invite_links.py`. Only owner/admin can view.
- **Revoke invite link**: ask for club_id and token. Then run `revoke_invite_link.py`. Only owner/admin can revoke.
- **My clubs**: run `my_clubs.py` to show all clubs.
- **Token**: you do not need to manage tokens — all scripts call `../hivo-identity/scripts/get_token.py hivo-club` automatically.
