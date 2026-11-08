# PTVault Deployment Guide

This guide covers two methods for packaging and deploying PTVault as a portable application on Linux.

## Table of Contents
1. [PyInstaller - Single Binary Executable](#pyinstaller-single-binary-executable)
2. [Docker - Containerized Deployment](#docker-containerized-deployment)
3. [Comparison](#comparison)
4. [Troubleshooting](#troubleshooting)

---

## PyInstaller - Single Binary Executable

PyInstaller packages PTVault into a single executable file that includes Python and all dependencies.

### Prerequisites
- Python 3.10+
- pip

### Building the Executable

1. **Install PyInstaller** (if not already installed):
   ```bash
   pip install pyinstaller
   ```

2. **Build the executable**:
   ```bash
   ./build_pyinstaller.sh
   ```

   This will:
   - Install PyInstaller if needed
   - Clean previous builds
   - Create a single executable at `dist/ptvault`

3. **Check the build**:
   ```bash
   ls -lh dist/ptvault
   ```

### Deploying the Executable

1. **Copy files to target system**:
   ```bash
   # Copy the executable
   cp dist/ptvault /opt/ptvault/

   # Copy configuration template
   cp .env.example /opt/ptvault/.env
   ```

2. **Configure environment**:
   ```bash
   cd /opt/ptvault
   nano .env  # Edit configuration
   ```

   Typical settings:
   ```env
   DATABASE_PATH=./data/ptvault.db
   ENVIRONMENT=production
   ```

   Leave `SECRET_KEY` and `JWT_SECRET_KEY` unset: PTVault generates them on
   first start and keeps them in `data/flask_secret.key` and
   `data/jwt_secret.key`. If you set them, PTVault refuses to start with a
   placeholder or a value shorter than 32 bytes.

3. **Run PTVault**:
   ```bash
   cd /opt/ptvault
   ./ptvault
   ```

   Access at: http://localhost:5001

### Creating a systemd Service

For production deployments, run PTVault as a systemd service:

1. **Create service file**:
   ```bash
   sudo nano /etc/systemd/system/ptvault.service
   ```

   ```ini
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

   # Security hardening
   PrivateTmp=true
   NoNewPrivileges=true
   ProtectSystem=strict
   ProtectHome=true
   ReadWritePaths=/opt/ptvault/data

   [Install]
   WantedBy=multi-user.target
   ```

2. **Create dedicated user**:
   ```bash
   sudo useradd -r -s /bin/false ptvault
   sudo chown -R ptvault:ptvault /opt/ptvault
   ```

3. **Enable and start service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ptvault
   sudo systemctl start ptvault
   ```

4. **Check status**:
   ```bash
   sudo systemctl status ptvault
   sudo journalctl -u ptvault -f  # View logs
   ```

### Pros and Cons

**Pros:**
- Single file distribution
- No Docker/container runtime needed
- Lower overhead
- Easy to transfer and run

**Cons:**
- Larger file size (~50-100 MB)
- May have compatibility issues across different Linux distributions
- Requires Python runtime libraries

---

## Docker - Containerized Deployment

Docker packages PTVault with all dependencies in an isolated container.

### Prerequisites
- Docker Engine 20.10+
- docker-compose (optional, but recommended)

### Installing Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**RHEL/CentOS:**
```bash
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

**Arch:**
```bash
sudo pacman -S docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

**Note:** Log out and back in for group changes to take effect.

### Building and Running with Docker

#### Option 1: Using docker-compose (Recommended)

1. **Configure environment**:
   ```bash
   cp .env.example .env
   nano .env  # Edit configuration
   ```

2. **Build and start**:
   ```bash
   docker compose up -d
   ```

3. **View logs**:
   ```bash
   docker compose logs -f
   ```

4. **Stop**:
   ```bash
   docker compose down
   ```

> **Notes**
> - The container runs with `ENVIRONMENT=production`, so session cookies are marked Secure and the Flask debugger is off. Browsers accept Secure cookies on `http://localhost`; to use PTVault from other machines, put it behind HTTPS (see [Behind Nginx Reverse Proxy](#behind-nginx-reverse-proxy)).
> - On macOS, port 5000 is often taken by AirPlay Receiver. Change the mapping in `docker-compose.yml` (for example `"127.0.0.1:5050:5000"`) if the container fails to bind.
> - The port is published on `127.0.0.1` only. To reach PTVault from other machines, put a TLS reverse proxy in front of it rather than publishing it on all interfaces.
> - The app runs as an unprivileged `ptvault` user (UID/GID 1000 by default), not root. `./data` must be writable by that user: build with `PTVAULT_UID=$(id -u) PTVAULT_GID=$(id -g) docker compose build`, or after upgrading from an image that ran as root, `sudo chown -R 1000:1000 ./data`.
> - Dependencies install from `requirements.lock` with `--require-hashes`, and the base image is pinned by digest.

#### Option 2: Using build script

1. **Build the image**:
   ```bash
   ./build_docker.sh build
   ```

2. **Run the container**:
   ```bash
   ./build_docker.sh run
   ```

3. **View logs**:
   ```bash
   ./build_docker.sh logs
   ```

4. **Stop the container**:
   ```bash
   ./build_docker.sh stop
   ```

#### Option 3: Manual Docker commands

1. **Build the image**:
   ```bash
   docker build -t ptvault:latest .
   ```

2. **Run the container**:
   ```bash
   mkdir -p ./data

   docker run -d \
     --name ptvault \
     -p 127.0.0.1:5000:5000 \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/.env:/app/.env:ro \
     --restart unless-stopped \
     ptvault:latest
   ```

3. **Access PTVault**:
   Open browser to http://localhost:5000

### Docker Management Commands

```bash
# View logs
docker logs -f ptvault

# Restart container
docker restart ptvault

# Stop container
docker stop ptvault

# Remove container
docker rm -f ptvault

# Open shell in container
docker exec -it ptvault /bin/bash

# View container stats
docker stats ptvault
```

### Production Deployment with Docker

#### Using Docker Swarm

1. **Initialize swarm**:
   ```bash
   docker swarm init
   ```

2. **Deploy as stack**:
   ```bash
   docker stack deploy -c docker-compose.yml ptvault
   ```

3. **Check services**:
   ```bash
   docker service ls
   docker service logs -f ptvault_ptvault
   ```

#### Behind Nginx Reverse Proxy

1. **Create nginx config**:
   ```nginx
   server {
       listen 80;
       server_name ptvault.example.com;

       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

2. **Enable HTTPS with Let's Encrypt**:
   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   sudo certbot --nginx -d ptvault.example.com
   ```

### Pros and Cons

**Pros:**
- Complete isolation from host system
- All dependencies included
- Consistent across all Linux distributions
- Easy to update and rollback
- Built-in health checks
- Better security through containerization

**Cons:**
- Requires Docker runtime
- Slightly higher resource overhead
- More complex setup for beginners
- Larger total size (base image + app)

---

## Comparison

| Feature | PyInstaller | Docker |
|---------|-------------|--------|
| **File Size** | ~50-100 MB | ~300-400 MB (image) |
| **Prerequisites** | Python libs | Docker Engine |
| **Portability** | High | High (self-contained) |
| **Resource Usage** | Lower | Slightly higher |
| **Isolation** | None | Full container |
| **Updates** | Replace binary | Pull new image |
| **Ease of Use** | Simple | Moderate |
| **Production Ready** | Yes | Yes |
| **Best For** | Quick deployment, pentesting laptops | Production servers, teams |

---

## Troubleshooting

### PyInstaller Issues

**Problem: "Permission denied" when running executable**
```bash
chmod +x ptvault
```

**Problem: Database errors on startup**
- Ensure the executable has write permissions to create `./data/` directory
- Check that .env file is in the same directory

### Docker Issues

**Problem: "Cannot connect to Docker daemon"**
```bash
# Start Docker service
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

**Problem: Port 5000 already in use**
```bash
# Change port in docker-compose.yml or docker run command
# docker-compose.yml:
ports:
  - "8080:5000"  # Change 8080 to desired port

# Or with docker run:
docker run -p 8080:5000 ...
```

**Problem: Database persists old data after rebuild**
```bash
# Remove the data volume
docker compose down -v

# Or manually remove data directory
rm -rf ./data
```

**Problem: Container exits immediately**
```bash
# Check logs for errors
docker logs ptvault

# Common issues:
# - Missing .env file
# - Invalid configuration
# - Port conflict
```

### General Issues

**Problem: Cannot access PTVault from other machines**

For PyInstaller (or `python app.py`), bind to all interfaces:
```bash
./ptvault -i 0.0.0.0 -p 5001
```

For Docker:
- Already configured to accept external connections
- Ensure firewall allows port 5000

**Problem: Forgot a password**
- Another admin can reset it from **Admin > Users**
- If the only admin is locked out there is no recovery path; with encryption enabled the database key is derived from the original setup password
- To start over, stop PTVault and delete `data/ptvault.db*`, `data/encryption.key` and `data/encryption.salt` (all data is lost)

---

## Security Recommendations

### For Both Deployments

1. **Keep the signing secrets private**: PTVault generates `SECRET_KEY` and
   `JWT_SECRET_KEY` into `data/` on first start. Anyone with these files can
   forge a login, so protect `data/` like the database. To set them yourself
   (for example, to share them across hosts), use at least 32 random bytes:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Restrict network access**:
   ```bash
   # Use firewall to limit access
   sudo ufw allow from 192.168.1.0/24 to any port 5000
   ```

3. **Use HTTPS in production**:
   - Deploy behind Nginx/Apache with SSL
   - Use Let's Encrypt for free certificates

4. **Regular backups**:
   ```bash
   # Backup database
   cp data/ptvault.db data/backups/ptvault-$(date +%Y%m%d).db

   # Backup evidence files
   tar -czf evidence-backup-$(date +%Y%m%d).tar.gz data/
   ```

5. **Keep updated**:
   ```bash
   # PyInstaller: Rebuild with latest code
   git pull
   ./build_pyinstaller.sh

   # Docker: Rebuild image
   git pull
   docker compose build
   docker compose up -d
   ```

---

## Next Steps

After deployment:

1. **Access PTVault**: http://localhost:5001 (Docker: http://localhost:5000)
2. **Complete setup**: Create the initial admin account
3. **Create engagement**: Start documenting findings
4. **Add evidence**: Upload screenshots, notes, tool output
5. **Tag and organize**: Use tags and host indicators

For questions or issues, visit: https://github.com/rseclabs/ptvault-oss
