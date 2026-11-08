# Security Policy

PTVault stores sensitive penetration-testing evidence, so security reports are taken seriously.

## Reporting a Vulnerability

**Please do not open a public issue for security problems.**

Report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" on the repository's **Security** tab).

Please include:

- The affected endpoint, file, or feature
- Steps to reproduce (a minimal proof of concept is ideal)
- The impact you believe it has
- The PTVault version or commit you tested

You should receive an acknowledgement within a few days. Once a fix is available,
a security advisory will be published crediting the reporter (unless you prefer
to stay anonymous).

## Supported Versions

Security fixes are made on the latest release on the `main` branch.

## Scope

In scope: the PTVault application code in this repository (authentication,
RBAC and engagement isolation, file upload and parsing, report export,
database encryption).

Out of scope: vulnerabilities in third-party tools PTVault bundles or
downloads (CyberChef, Atomic Red Team) — please report those upstream —
and issues that require an already-compromised host.

## Deployment Guidance

PTVault is designed for local or trusted-network use. If it is reachable by
others, run it behind HTTPS, protect `data/` (it holds the generated
`SECRET_KEY` / `JWT_SECRET_KEY` files), and back up `data/encryption.key` and `data/encryption.salt`
alongside the database. See [DEPLOYMENT.md](DEPLOYMENT.md).
