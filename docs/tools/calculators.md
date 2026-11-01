# Calculators

The Calculators sub-tab includes two tools: the CVSS 3.1 Calculator for scoring vulnerabilities and the Subnet Calculator for network address computations.

## CVSS 3.1 Calculator

The Common Vulnerability Scoring System (CVSS) 3.1 calculator lets you score vulnerabilities using the industry-standard Base Metrics without memorizing the specification.

### Accessing

Click **Tools** → **Calculators** → **CVSS 3.1**.

### Base Metrics

Configure all eight base metrics by clicking the appropriate value for each:

| Metric | Options | Description |
|--------|---------|-------------|
| **Attack Vector (AV)** | Network (N), Adjacent (A), Local (L), Physical (P) | How the vulnerability is exploited |
| **Attack Complexity (AC)** | Low (L), High (H) | Conditions beyond attacker control required |
| **Privileges Required (PR)** | None (N), Low (L), High (H) | Authentication level needed |
| **User Interaction (UI)** | None (N), Required (R) | Whether a victim must take action |
| **Scope (S)** | Unchanged (U), Changed (C) | Whether impact extends beyond the vulnerable component |
| **Confidentiality Impact (C)** | None (N), Low (L), High (H) | Impact on data confidentiality |
| **Integrity Impact (I)** | None (N), Low (L), High (H) | Impact on data integrity |
| **Availability Impact (A)** | None (N), Low (L), High (H) | Impact on system availability |

### Score Display

The calculated CVSS score and severity label update in real time as you select metrics:

| Score Range | Severity | Color |
|-------------|----------|-------|
| 0.0 | None | Gray |
| 0.1–3.9 | Low | Blue |
| 4.0–6.9 | Medium | Yellow |
| 7.0–8.9 | High | Orange |
| 9.0–10.0 | Critical | Red |

### CVSS Vector String

The full CVSS vector string is shown below the score (e.g., `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`). Click **Copy Vector** to copy it to your clipboard.

### Using in Reports

Copy the score and vector string to paste into your writeup. The [CVSS Score Card](../reporting/format-tools.md#cvss-score-card) format tool in the report builder can display this visually.

---

## Subnet Calculator

Calculate network addressing information from an IP address and subnet mask or CIDR prefix.

### Accessing

Click **Tools** → **Calculators** → **Subnet**.

### Inputs

| Field | Description | Example |
|-------|-------------|---------|
| **IP Address** | Any IP address in the subnet | `192.168.1.100` |
| **CIDR / Mask** | CIDR prefix length or subnet mask | `/24` or `255.255.255.0` |

### Quick Presets

Click a preset button to quickly populate common masks:

| Preset | CIDR | Addresses | Common Use |
|--------|------|-----------|-----------|
| /8 | 255.0.0.0 | 16,777,214 | Class A networks |
| /16 | 255.255.0.0 | 65,534 | Class B networks |
| /24 | 255.255.255.0 | 254 | Class C / common LAN |
| /25 | 255.255.255.128 | 126 | Split /24 |
| /27 | 255.255.255.224 | 30 | Small segments |
| /30 | 255.255.255.252 | 2 | Point-to-point links |

### Output

| Field | Description |
|-------|-------------|
| **Network Address** | First address of the subnet |
| **Broadcast Address** | Last address of the subnet |
| **First Usable IP** | First host address (network + 1) |
| **Last Usable IP** | Last host address (broadcast - 1) |
| **Subnet Mask** | Full subnet mask in dotted-decimal |
| **Wildcard Mask** | Inverse of subnet mask (used in ACLs) |
| **Usable Hosts** | Number of addresses available for hosts |

Each output field has a **Copy** button to copy the value to your clipboard.

### Use Cases

- Define scope boundaries for an engagement
- Verify CIDR notation in evidence and reports
- Plan network segmentation analysis
- Calculate ranges for Nmap scan commands
