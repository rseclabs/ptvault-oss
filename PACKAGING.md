# PTVault Packaging Options - Quick Reference

PTVault can be packaged for Linux deployment using two methods:

## 🚀 Quick Start

### Option 1: PyInstaller (Single Binary)
```bash
./build_pyinstaller.sh
# Creates: dist/ptvault
```

**When to use:**
- Quick deployment to pentesting laptops
- Offline systems without Docker
- Minimal dependencies
- Single-user scenarios

### Option 2: Docker (Container)
```bash
./build_docker.sh build
./build_docker.sh run
# Or: docker-compose up -d
```

**When to use:**
- Production servers
- Team deployments
- Consistent environments
- Isolated/secure deployments

## 📦 What's Included

Both packaging methods include complete documentation:

- **DEPLOYMENT.md** - Full deployment guide with:
  - Step-by-step instructions for both methods
  - Production deployment configurations
  - systemd service setup
  - Nginx reverse proxy configuration
  - Security recommendations
  - Troubleshooting guide

## 🔧 Files Created

### PyInstaller
- `ptvault.spec` - PyInstaller specification
- `build_pyinstaller.sh` - Build script
- `.env.example` - Configuration template

### Docker
- `Dockerfile` - Container image definition
- `docker-compose.yml` - Compose configuration
- `build_docker.sh` - Build and management script
- `.dockerignore` - Build optimization

## 📊 Comparison

| Feature | PyInstaller | Docker |
|---------|-------------|--------|
| Size | ~50-100 MB | ~300-400 MB |
| Setup Time | 2 minutes | 5 minutes |
| Dependencies | None | Docker Engine |
| Isolation | None | Full |
| Best For | Laptops | Servers |

## 🎯 Recommendations

**For Penetration Testers:**
- Use PyInstaller for portability
- Easy to carry on USB drive
- No Docker daemon needed

**For Organizations:**
- Use Docker for production
- Better security and isolation
- Easier updates and scaling

## 📖 Full Documentation

See **DEPLOYMENT.md** for complete instructions, troubleshooting, and production configurations.

## 🔒 Security Notes

Both methods:
- Use Argon2id password hashing for authentication
- Require strong secret key configuration
- Should be deployed behind HTTPS in production
- Include security hardening options

## ⚡ Quick Commands

**PyInstaller:**
```bash
# Build
./build_pyinstaller.sh

# Run
./dist/ptvault

# Deploy as service
sudo cp dist/ptvault /opt/ptvault/
sudo systemctl enable ptvault
```

**Docker:**
```bash
# Build and run
./build_docker.sh build
./build_docker.sh run

# View logs
./build_docker.sh logs

# Stop
./build_docker.sh stop

# Or use docker-compose
docker-compose up -d
docker-compose logs -f
docker-compose down
```

## 🆘 Getting Help

- Full guide: See DEPLOYMENT.md
- Issues: https://github.com/rseclabs/ptvault-oss/issues
- Docker not starting: Check `docker logs ptvault`
- PyInstaller errors: Check build output for missing dependencies
