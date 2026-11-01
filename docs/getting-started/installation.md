# Installation

PTVault requires Python 3.10+ (or Docker) and runs on Linux, macOS and Windows. Choose the method that fits your environment.

## Method 1: Python (Recommended for Local Use)

### 1. Clone or Download PTVault

```bash
git clone https://github.com/rseclabs/ptvault-oss.git
cd ptvault-oss
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# .\venv\Scripts\activate       # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the Server

```bash
python app.py
```

The server starts on `http://localhost:5001`. Open that URL in your browser to complete [First-Time Setup](./first-time-setup.md).

---

## Method 2: Docker

If you prefer an isolated container environment:

```bash
git clone https://github.com/rseclabs/ptvault-oss.git
cd ptvault-oss
cp .env.example .env          # docker-compose.yml mounts this file
docker compose up -d
```

Access PTVault at `http://localhost:5000`. Data is stored in `./data` on the host. On macOS, port 5000 may already be used by AirPlay Receiver; change the mapping in `docker-compose.yml` (for example `"5050:5000"`).

See the [Deployment Guide](../../DEPLOYMENT.md) for full Docker configuration options.

---

## Method 3: PyInstaller Binary

Build a standalone executable from source (on the same OS and architecture you will run it on):

```bash
./build_pyinstaller.sh
./dist/ptvault
```

The resulting binary needs no Python installation on the target machine. Ideal for pentesting laptops.

---

## System Requirements

| Component | Minimum |
|-----------|---------|
| Python | 3.10+ |
| RAM | 512 MB |
| Disk | 200 MB (plus evidence storage) |
| Browser | Chrome 90+, Firefox 88+, Edge 90+ |

### Database Encryption

Encryption works out of the box: `requirements.txt` installs `sqlcipher3`, whose prebuilt wheels include SQLCipher for Linux, macOS and Windows. The database is encrypted when you create the first admin account. If `sqlcipher3` cannot be installed, PTVault still runs with an unencrypted SQLite database and logs `SQLCipher encryption: DISABLED`.

### Optional: PDF Export Libraries

Server-side PDF export uses WeasyPrint, which needs the Pango library:

```bash
# Debian / Ubuntu / Kali
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0

# Fedora / RHEL
sudo dnf install -y pango

# macOS
brew install pango
```

Without Pango, PDF export falls back to the browser's print dialog. The Docker image already includes it.

---

## Configuration

Copy the example environment file and customize if needed:

```bash
cp .env.example .env
```

For development use, no changes are required — PTVault auto-generates secret keys on first run.

For production deployments, set explicit secret keys:

```bash
# Generate a random SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate a random JWT_SECRET_KEY
python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Flask session encryption key |
| `DATABASE_PATH` | `./data/ptvault.db` | Path to the SQLite database file |
| `JWT_SECRET_KEY` | Auto-generated | JWT token signing key |
| `JWT_EXPIRY_HOURS` | `24` | How long login sessions last |
| `ENVIRONMENT` | `development` | Set to `production` for secure cookies |
| `PTVAULT_ENCRYPTION_REQUIRED` | *(not set)* | If set, prevents disabling DB encryption |

---

## Next Steps

Once the server is running, proceed to [First-Time Setup](./first-time-setup.md) to create your admin account.
