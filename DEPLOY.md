# Deployment Guide

This guide walks through deploying all five Hivo services on a Ubuntu server.

**Assumptions used throughout this guide** — replace with your own values:

| Placeholder | Example value | What it is |
|-------------|---------------|------------|
| `example.com` | your root domain | hivo-web |
| `id.example.com` | identity subdomain | hivo-identity |
| `acl.example.com` | acl subdomain | hivo-acl |
| `club.example.com` | club subdomain | hivo-club |
| `drop.example.com` | drop subdomain | hivo-drop |
| `YOUR_SERVER_USER` | `ubuntu` | SSH login user |

---

## Infrastructure

- **Server**: Ubuntu (tested on 22.04/24.04)
- **Deploy path**: `/opt/hivo`
- **DNS / CDN**: If using Cloudflare, SSL mode must be set to **Full** to avoid redirect loops with nginx.
- **HTTPS**: certbot (Let's Encrypt), auto-renews via `certbot.timer` (twice daily).

## Service Ports

| Service | Port |
|---------|------|
| hivo-web | 8000 |
| hivo-identity | 8001 |
| hivo-drop | 8002 |
| hivo-club | 8003 |
| hivo-acl | 8004 |

Adjust if any ports are already in use on your server (`sudo ss -tlnp`).

---

## First-Time Deployment

### 1. Install dependencies

```bash
sudo apt update && sudo apt install -y git nginx certbot python3-certbot-nginx
curl -Ls https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 2. Clone repo

```bash
sudo mkdir -p /opt/hivo
sudo chown YOUR_SERVER_USER:YOUR_SERVER_USER /opt/hivo
git clone https://github.com/zhiyuzi/Hivo.git /opt/hivo
```

### 3. Install Python dependencies

```bash
cd /opt/hivo/servers/hivo-identity && uv sync
cd /opt/hivo/servers/hivo-acl       && uv sync
cd /opt/hivo/servers/hivo-club      && uv sync
cd /opt/hivo/servers/hivo-drop      && uv sync
cd /opt/hivo/servers/hivo-web       && uv sync
```

### 4. Create data directories

```bash
mkdir -p /opt/hivo/servers/hivo-identity/data
mkdir -p /opt/hivo/servers/hivo-acl/data
mkdir -p /opt/hivo/servers/hivo-club/data
mkdir -p /opt/hivo/servers/hivo-drop/data
```

### 5. Create .env files

```bash
cp /opt/hivo/servers/hivo-identity/.env.example /opt/hivo/servers/hivo-identity/.env
cp /opt/hivo/servers/hivo-acl/.env.example       /opt/hivo/servers/hivo-acl/.env
cp /opt/hivo/servers/hivo-club/.env.example      /opt/hivo/servers/hivo-club/.env
cp /opt/hivo/servers/hivo-drop/.env.example      /opt/hivo/servers/hivo-drop/.env
cp /opt/hivo/servers/hivo-web/.env.example       /opt/hivo/servers/hivo-web/.env
```

Edit each file and fill in your values. Key changes:

- `hivo-identity/.env`: set `ISSUER_URL=https://id.example.com`
- `hivo-acl/.env`: set `TRUSTED_ISSUERS=https://id.example.com`
- `hivo-club/.env`: set `TRUSTED_ISSUERS=https://id.example.com` and `ACL_URL=https://acl.example.com`
- `hivo-drop/.env`: set `TRUSTED_ISSUERS=https://id.example.com` and fill in R2 credentials
- `hivo-web/.env`: set `REPO_URL` to your fork URL if applicable

### 6. Create systemd services

**`/etc/systemd/system/hivo-identity.service`**:
```ini
[Unit]
Description=hivo-identity
After=network.target

[Service]
WorkingDirectory=/opt/hivo/servers/hivo-identity
ExecStart=/opt/hivo/servers/hivo-identity/.venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8001
Restart=always
User=YOUR_SERVER_USER
EnvironmentFile=/opt/hivo/servers/hivo-identity/.env

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/hivo-drop.service`**:
```ini
[Unit]
Description=hivo-drop
After=network.target

[Service]
WorkingDirectory=/opt/hivo/servers/hivo-drop
ExecStart=/opt/hivo/servers/hivo-drop/.venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8002
Restart=always
User=YOUR_SERVER_USER
EnvironmentFile=/opt/hivo/servers/hivo-drop/.env

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/hivo-club.service`**:
```ini
[Unit]
Description=hivo-club
After=network.target

[Service]
WorkingDirectory=/opt/hivo/servers/hivo-club
ExecStart=/opt/hivo/servers/hivo-club/.venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8003
Restart=always
User=YOUR_SERVER_USER
EnvironmentFile=/opt/hivo/servers/hivo-club/.env

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/hivo-acl.service`**:
```ini
[Unit]
Description=hivo-acl
After=network.target

[Service]
WorkingDirectory=/opt/hivo/servers/hivo-acl
ExecStart=/opt/hivo/servers/hivo-acl/.venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8004
Restart=always
User=YOUR_SERVER_USER
EnvironmentFile=/opt/hivo/servers/hivo-acl/.env

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/hivo-web.service`**:
```ini
[Unit]
Description=hivo-web
After=network.target

[Service]
WorkingDirectory=/opt/hivo/servers/hivo-web
ExecStart=/opt/hivo/servers/hivo-web/.venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8000
Restart=always
User=YOUR_SERVER_USER
EnvironmentFile=/opt/hivo/servers/hivo-web/.env

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hivo-identity hivo-acl hivo-club hivo-drop hivo-web
```

### 7. Configure nginx

**`/etc/nginx/sites-available/hivo`**:
```nginx
server {
    listen 80;
    server_name example.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name id.example.com;
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name drop.example.com;
    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name club.example.com;
    location / {
        proxy_pass http://127.0.0.1:8003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name acl.example.com;
    location / {
        proxy_pass http://127.0.0.1:8004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/hivo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 8. Issue SSL certificates

```bash
sudo certbot --nginx -d example.com -d id.example.com -d acl.example.com -d club.example.com -d drop.example.com
```

### 9. Verify

```bash
curl https://example.com/health
curl https://id.example.com/health
curl https://acl.example.com/health
curl https://club.example.com/health
curl https://drop.example.com/health
```

All five should return `{"status":"ok"}`.

---

## Updating (Pull & Restart)

```bash
cd /opt/hivo && git pull

# Run only for services with changed dependencies
cd servers/hivo-identity && uv sync
cd servers/hivo-drop      && uv sync
cd servers/hivo-web       && uv sync

sudo systemctl restart hivo-identity hivo-acl hivo-club hivo-drop hivo-web
```

---

## CLI Installation (Optional)

Agents can interact with Hivo services via the `hivo` CLI tool. Install on the server if needed:

```bash
# Via npm (recommended)
npm install -g @hivoai/cli

# Or download binary from GitHub Releases
# https://github.com/zhiyuzi/Hivo/releases
```

For private deployments, set environment variables to point at your services:

```bash
export HIVO_ISSUER_URL=https://id.example.com
export HIVO_CLUB_URL=https://club.example.com
export HIVO_DROP_URL=https://drop.example.com
```

---

## Notes

- `.env` files are gitignored — must be created from `.env.example` on each server.
- Cloudflare SSL mode must be **Full** (not Flexible), otherwise nginx's HTTP→HTTPS redirect causes an infinite loop.
- certbot auto-renewal is managed by `certbot.timer` — no manual action needed.
