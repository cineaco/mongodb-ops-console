# Security Policy

## Security Model & Master Key Architecture

MongoDB Ops Console stores SSH private keys and administrative database credentials using **AES-256-GCM** encryption. 

### Operational Security Requirements

1. **Master Key**:
   - Secrets are encrypted using `MASTER_KEY`. Always provide a 32-byte Base64-encoded string via environment variable (`MASTER_KEY`). Never commit `.env` files to git.
2. **SSH StrictHostKeyChecking**:
   - By default, Ansible deployment uses `StrictHostKeyChecking=no` to allow initial automated setup on dynamic infrastructure. Ensure your deployment network or VPC uses private subnet access or security groups to mitigate Man-In-The-Middle (MITM) risks.
3. **Admin Passwords**:
   - Initial deployment seeds an `admin` user. Always change default credentials immediately upon first login.
4. **CORS & Cookies**:
   - Configure `CORS_ALLOWED_ORIGINS` to exact trusted origins in production (do NOT allow `*` when `allow_credentials=True`).

## Reporting a Vulnerability

If you discover a security vulnerability within MongoDB Ops Console, please submit your findings to the security maintainers:

- **Do NOT** open a public GitHub issue for security vulnerabilities.
- Send a report describing the vulnerability, affected components, steps to reproduce, and any proof-of-concept details.
- We will acknowledge receipt of your report within 48 hours and provide status updates as we work on a fix.
