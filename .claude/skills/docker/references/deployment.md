# Deployment Reference

## Contents
- Production Configuration
- Reverse Proxy Setup
- Systemd Service
- PyInstaller Alternative
- Security Checklist
- Troubleshooting

## Production Configuration

### Environment Variables

PTVault reads config from `.env` via `config.py`. See the **flask** skill for how `Config` class loads these.

```bash
# .env for production — NEVER use defaults in production
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET_KEY=$(python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
DATABASE_PATH=/app/data/ptvault.db
ENVIRONMENT=production
JWT_EXPIRY_HOURS=8
```

### WARNING: Default or Weak Secrets

**The Problem:**

```bash
# BAD - Predictable secrets
SECRET_KEY=development
JWT_SECRET_KEY=secret123
```

**Why This Breaks:**
1. JWT tokens can be forged — attacker creates admin sessions. See the **jwt** skill.
2. Flask session cookies become predictable
3. Every PTVault instance with the default key shares the same auth

**The Fix:** Generate cryptographically random values at deploy time. NEVER reuse keys across environments.

## Reverse Proxy Setup

### Nginx with HTTPS

```nginx
server {
    listen 80;
    server_name ptvault.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ptvault.example.com;

    ssl_certificate /etc/letsencrypt/live/ptvault.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ptvault.example.com/privkey.pem;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Must match Config.MAX_FILE_SIZE (250MB)
    client_max_body_size 250M;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### WARNING: Mismatched Upload Limits

**The Problem:** Nginx default `client_max_body_size` is 1MB. PTVault allows 250MB evidence uploads (`Config.MAX_FILE_SIZE`). Users get `413 Request Entity Too Large` with no useful error message.

**The Fix:** Set `client_max_body_size 250M;` in nginx to match the Flask config.

### Enable HTTPS

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d ptvault.example.com
```

## Systemd Service

### Docker Compose as Service

```ini
# /etc/systemd/system/ptvault.service
[Unit]
Description=PTVault Container
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ptvault
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

### PyInstaller Binary as Service

```ini
# /etc/systemd/system/ptvault.service
[Unit]
Description=PTVault Penetration Testing Evidence Manager
After=network.target

[Service]
Type=simple
User=ptvault
Group=ptvault
WorkingDirectory=/opt/ptvault
ExecStart=/opt/ptvault/ptvault
Restart=on-failure
RestartSec=5s
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/ptvault/data

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
sudo useradd -r -s /bin/false ptvault
sudo chown -R ptvault:ptvault /opt/ptvault
sudo systemctl daemon-reload
sudo systemctl enable ptvault
sudo systemctl start ptvault
sudo journalctl -u ptvault -f  # Tail logs
```

## PyInstaller Alternative

For air-gapped environments or pentesting laptops without Docker:

```bash
./build_pyinstaller.sh   # Prompts for regular or time-limited build
# Creates: dist/ptvault

# Deploy
cp dist/ptvault /opt/ptvault/
cp .env.example /opt/ptvault/.env
cd /opt/ptvault && ./ptvault
```


## Security Checklist

Copy this checklist for production deployments:
- [ ] Generate unique `SECRET_KEY` (64+ hex chars)
- [ ] Generate unique `JWT_SECRET_KEY` (32+ bytes base64)
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure firewall — allow only 80/443 (or 5000 for direct access)
- [ ] Enable HTTPS with valid certificate
- [ ] Set `client_max_body_size 250M` in nginx
- [ ] Run container as non-root user
- [ ] Mount data volume with correct permissions
- [ ] Set up automated backups (see monitoring reference)
- [ ] Configure log rotation
- [ ] Test restore from backup

## Troubleshooting

### Container Won't Start

```bash
docker-compose logs ptvault
# Common: missing .env, port conflict, data dir permissions
```

### Database Locked Errors

SQLite WAL mode allows concurrent reads but only one writer. NEVER run multiple containers against the same database file. See the **sqlite** skill.

```bash
# Check for zombie processes
docker exec ptvault ps aux | grep python

# Force restart
docker-compose down && docker-compose up -d
```

### Cannot Access from Network

```bash
# Verify binding
docker exec ptvault ss -tlnp

# Check firewall
sudo ufw status
sudo ufw allow 5000/tcp
```

### Forgot Master Password

No recovery mechanism by design (see the **argon2** skill). Delete `data/ptvault.db` and restart — all data is lost.
