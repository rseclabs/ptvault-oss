# Nmap Parser

The Nmap parser imports XML output from Nmap network scans, automatically creating hosts and populating their open ports with service information.

## Generating the Nmap XML File

Run Nmap with the `-oX` flag to save output in XML format:

```bash
# Basic TCP scan with service detection
nmap -sV -oX scan.xml 192.168.1.0/24

# Comprehensive scan with OS detection and scripts
nmap -sV -O -sC -oX scan.xml 192.168.1.0/24

# Full port range scan
nmap -sV -p- -oX scan.xml 192.168.1.0/24

# UDP and TCP
nmap -sU -sV -oX scan.xml 192.168.1.0/24
```

The output file will have a `.xml` extension and begin with the `<nmaprun>` XML root element.

## Importing into PTVault

1. Click the **Hosts** tab and ensure the correct engagement is active
2. Click **Import** (or use **+ Add Evidence** and select **Tool Output**)
3. Select your `.xml` Nmap file
4. Click **Upload**
5. PTVault parses the file and displays a summary of what was imported

## What Gets Extracted

| Data | Where It Goes |
|------|--------------|
| Host IP addresses | New host records in the host list |
| Host hostnames | Set as the hostname for each host record |
| OS detection results | Stored in the host's OS field |
| Open ports | Added to each host's Open Ports tab |
| Filtered ports | Added with state `filtered` |
| Service names | Stored in the port's Service field |
| Service versions | Stored in the port's Version field |
| Protocol (tcp/udp) | Stored in the port's Protocol field |
| Script output | Stored in evidence metadata |

## Automatic Tags

Evidence items created from Nmap imports are automatically tagged with:
- `nmap`
- `port-scan`
- `network-scan`

## Duplicate Handling

If an Nmap scan includes hosts already in PTVault:
- Existing host records are **updated** with new port data
- New ports are added; existing ports with the same number/protocol are updated
- The host IP is used as the unique identifier for matching

## Example

After importing a scan of a `/24` network, the host list will populate with all discovered hosts. Click any host to see its open ports:

| Port | Protocol | State | Service | Version |
|------|----------|-------|---------|---------|
| 22 | tcp | open | ssh | OpenSSH 8.9p1 Ubuntu |
| 80 | tcp | open | http | Apache httpd 2.4.52 |
| 443 | tcp | open | https | Apache httpd 2.4.52 |
| 3306 | tcp | filtered | mysql | — |

## Troubleshooting

**"File format not recognized"**
Verify the file is a valid Nmap XML export (not a greppable or normal text format). The file must start with the `<nmaprun>` element.

**"No hosts found"**
The scan may have found no live hosts, or all hosts were filtered. Check that the Nmap scan actually ran successfully and produced results.

**"Duplicate hosts"**
PTVault matches by IP address. If you have hosts with the same IP from different scans, the later import updates the existing record.
