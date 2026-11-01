# Command Hub

The Command Hub centralizes commonly used penetration testing resources: shell one-liners, a searchable command reference, and a Markdown syntax guide.

## Accessing the Command Hub

Click **Tools** → **Command Hub**.

The Command Hub has four sub-tabs:

---

## Shells

A library of shell one-liners organized by language and technique.

### Categories

| Category | Description |
|----------|-------------|
| **Shells** | Bind shells and spawn shell commands |
| **Reverse Shells** | One-liner reverse shell commands by language |
| **Shell Upgrades** | Commands to upgrade a basic shell to a full TTY |

### Reverse Shell Languages

Includes one-liners for: Bash, Python, Perl, PHP, Ruby, Netcat, PowerShell, Socat, Awk, Java, and more.

### Using a Shell One-Liner

1. Browse or search for the desired shell type
2. Click the command to copy it to your clipboard
3. Replace **LHOST** and **LPORT** variables with your listener details
4. Run on the target system

### Variable Substitution

Some one-liners have labeled variables (e.g., `{{LHOST}}`, `{{LPORT}}`). Click the variable fields to enter your values, and the command updates automatically with the substituted values.

### Managing Shell One-Liners *(Admin)*

Admins can add, edit, and delete shell one-liners via **Admin > Shell One-Liners**. See [Admin: Shell One-Liners](../admin/README.md#shell-one-liners).

---

## Command Reference

A searchable database of penetration testing commands organized by phase.

### Categories

| Category | Examples |
|----------|---------|
| **Recon** | DNS enumeration, WHOIS, subdomain discovery |
| **Enumeration** | Nmap, SMB enumeration, web directory brute-force |
| **Exploitation** | SQLi payloads, LFI/RFI, command injection |
| **Post-Exploitation** | Privilege escalation, persistence, lateral movement |
| **Reporting** | Evidence collection, screenshot tools |

### Searching Commands

Type in the search bar to filter commands by name, command text, or description. Results update in real time.

### Copying Commands

Click any command to copy it to your clipboard. The usage counter increments each time a command is copied.

### Favorites

Click the **star icon** on any command to mark it as a favorite. Favorited commands appear at the top of their category.

### Custom Commands

Create your own commands alongside the built-in library:

1. Click **+ New Command**
2. Enter:
   - **Name**: Short descriptive name
   - **Category**: Which phase this command belongs to
   - **Command**: The actual command text (use `{{VARIABLE}}` for dynamic fields)
   - **Description**: When and why to use this command
3. Click **Save**

Custom commands can be **edited** and **deleted**. Built-in pre-seeded commands are read-only.

---

## Markdown Reference

A quick-reference cheatsheet for Markdown syntax. Use this when writing evidence notes, writeups, or report content in PTVault.

### Included Reference Sections

- Headings (H1–H6)
- Emphasis (bold, italic, strikethrough)
- Lists (ordered, unordered, nested)
- Links and images
- Inline and fenced code blocks
- Blockquotes
- Tables
- Horizontal rules

---

## Also in Command Hub: MSFVenom Builder

The MSFVenom payload builder is also accessed via the Command Hub sub-tab. See [MSFVenom Builder](./msfvenom-builder.md).
