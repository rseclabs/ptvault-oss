# CyberChef

CyberChef is an open-source data transformation tool developed by GCHQ. PTVault embeds a local copy of CyberChef, allowing you to use it without an internet connection.

## What is CyberChef?

CyberChef is a "Swiss Army knife" for data transformations. It supports hundreds of operations including:

- **Encoding/Decoding**: Base64, URL, HTML, Hex, Binary, ROT13, and more
- **Hashing**: MD5, SHA-1, SHA-256, SHA-512, bcrypt, and more
- **Encryption/Decryption**: AES, DES, RSA, XOR, and more
- **Compression**: Gzip, Zip, Brotli, Zlib
- **Parsing**: JSON, XML, CSV, JWT, X.509 certificates
- **Network**: IP to decimal, CIDR range expand, MAC address analysis
- **Code analysis**: Regular expressions, string extraction, character counting

## Accessing CyberChef

Click **Tools** → **CyberChef** in the navigation.

CyberChef loads directly in the PTVault interface. If CyberChef is not installed, you will see an option to install it.

## Installing CyberChef *(Admin)*

CyberChef must be installed by an admin before it can be used:

1. Go to **Admin > Settings**
2. Find the **CyberChef** section
3. Click **Install CyberChef**
4. PTVault downloads the latest version from GitHub automatically
5. Once installed, CyberChef is available to all users

## Updating CyberChef *(Admin)*

1. Go to **Admin > Settings** → CyberChef section
2. Click **Check for Updates**
3. If a newer version is available, click **Update**

## Using CyberChef

CyberChef operates as a "recipe" builder:

1. **Input**: Paste or type your data in the Input box
2. **Operations**: Search for and add operations in the left panel
3. **Recipe**: Operations are chained in the Recipe column
4. **Output**: The transformed result appears automatically in the Output box

CyberChef supports baking (applying the recipe) automatically or manually.

## Common Use Cases in Penetration Testing

| Task | Operations to Use |
|------|-----------------|
| Decode base64-encoded malware | From Base64 |
| Encode a payload for delivery | To Base64 (or To Hex) |
| Analyze a JWT token | JWT Decode |
| Identify hash type | Identify hash |
| Encode URL parameters | URL Encode |
| Decode URL-encoded data | URL Decode |
| XOR decode obfuscated data | XOR |
| Analyze encoded PowerShell | From Base64 → Decode text |
| Extract strings from binary | Strings |
| Convert hex shellcode | From Hex |

## Offline Use

Once installed, CyberChef runs entirely in your browser. No internet connection is required. The CyberChef files are served by the PTVault Flask server from local storage.
