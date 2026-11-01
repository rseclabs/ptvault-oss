# Installation

PTVault requires Python 3.10+ and can be installed with a few commands. Choose the method that fits your environment.

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
docker-compose up -d
```

Access PTVault at `http://localhost:5000`.

See the [Deployment Guide](../../DEPLOYMENT.md) for full Docker configuration options.

---

## Method 3: PyInstaller Binary

A pre-built standalone executable is available for Linux:

```bash
./build_pyinstaller.sh
./dist/ptvault
```

No Python installation required on the target machine. Ideal for pentesting laptops.

---

## System Requirements

| Component | Minimum |
|-----------|---------|
| Python | 3.10+ |
| RAM | 512 MB |
| Disk | 200 MB (plus evidence storage) |
| Browser | Chrome 90+, Firefox 88+, Edge 90+ |

### Optional: SQLCipher for Database Encryption

Database encryption requires the `pysqlcipher3` package and the `sqlcipher` system library:

```bash
# Debian / Ubuntu / Kali
sudo apt-get install -y sqlcipher libsqlcipher-dev python3-dev
pip install pysqlcipher3

# Fedora / RHEL
sudo dnf install -y sqlcipher sqlcipher-devel python3-devel
pip install pysqlcipher3
```

Without SQLCipher, PTVault runs normally with an unencrypted SQLite database. The encryption option in Admin settings will show as unavailable.

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
