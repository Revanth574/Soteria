# Soteria H1-7a Production VM Runbook

Target:
- Ubuntu 24.04 LTS
- GCP e2-micro, asia-south1
- Static IP: `34.14.190.8`
- Domains: `soteria.co.in`, `www.soteria.co.in`
- App code: `/opt/soteria`
- Persistent data: `/var/lib/soteria`
- App user: `soteria`

Run every command below on the VM unless the section says local machine.

## 1. Connect

```bash
gcloud compute ssh INSTANCE_NAME --zone asia-south1-a
```

If using the GCP Console SSH button, start at section 2 after the shell opens.

## 2. Confirm OS And Python

```bash
lsb_release -a
python3 --version
```

Ubuntu 24.04 should report Python 3.12+.

## 3. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip ca-certificates curl gnupg
```

Install Caddy from the official apt repository:

```bash
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/caddy-stable-archive-keyring.gpg
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install -y caddy
caddy version
```

## 4. Create User And Persistent Directories

```bash
sudo useradd --system --home /var/lib/soteria --shell /usr/sbin/nologin soteria || true
sudo mkdir -p /var/lib/soteria/sessions
sudo mkdir -p /var/www/soteria-public-pages/policies
sudo chown -R soteria:soteria /var/lib/soteria
sudo chmod 0750 /var/lib/soteria
sudo chmod 0750 /var/lib/soteria/sessions
```

Do not delete `/var/lib/soteria` during clean deploys. It contains `soteria_dev.db` and anonymous session artifacts.

## 5. Clone Or Update Code

If the VM needs a GitHub deploy key, create it once on the VM:

```bash
ssh-keygen -t ed25519 -C "soteria-deploy" -f ~/.ssh/soteria_deploy_key -N ""
cat ~/.ssh/soteria_deploy_key.pub
```

This creates two files:
- `~/.ssh/soteria_deploy_key` as the private key, which never leaves the VM.
- `~/.ssh/soteria_deploy_key.pub` as the public key, which goes into GitHub as
  the deploy key.

Use the public key in GitHub first, then clone with SSH if you prefer deploy-key
auth over HTTPS.

First deploy:

```bash
sudo mkdir -p /opt
sudo chown "$(id -un):$(id -gn)" /opt
git clone --branch main git@github.com:Revanth574/Soteria.git /opt/soteria
```

Redeploy:

```bash
cd /opt/soteria
git pull --ff-only origin main
```

## 6. Install Python Dependencies

```bash
cd /opt/soteria/backend
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

This installs from the committed `backend/pyproject.toml`; do not hand-pick dependency versions on the VM.

## 7. Provide Prompt Assets

The repository contains the combined prompt asset at
`/opt/soteria/prompts/extract_policy_v1.2.md`. The app splits that file into
system and extraction portions at startup using the `## EXTRACTION TASK`
divider. No separate `system.md` file is required on the VM. When
`SOTERIA_COMBINED_PROMPT_PATH` is set, the app uses it and ignores the older
two-file prompt variables.

## 8. Create Production Environment File

```bash
sudo tee /opt/soteria/backend/.env >/dev/null <<'EOF'
ANTHROPIC_API_KEY=<PASTE_REAL_KEY_ON_VM_ONLY>
ANTHROPIC_MODEL=<PASTE_PRODUCTION_CLAUDE_MODEL>
ANTHROPIC_MAX_TOKENS=16000
SOTERIA_COMBINED_PROMPT_PATH=/opt/soteria/prompts/extract_policy_v1.2.md
DATABASE_URL=sqlite:////var/lib/soteria/soteria_dev.db
EPHEMERAL_DATA_DIR=/var/lib/soteria
EPHEMERAL_TTL_SECONDS=86400
MAX_UPLOAD_BYTES=26214400
ANONYMOUS_UPLOADS_PER_IP_PER_HOUR=5
TRUST_PROXY_HEADERS=true
EOF
sudo chown soteria:soteria /opt/soteria/backend/.env
sudo chmod 0640 /opt/soteria/backend/.env
```

Never commit this file or paste the real API key into logs or tickets.

`ANTHROPIC_TEMPERATURE` is optional. Leave it unset for Claude models that
reject the parameter, such as `claude-sonnet-5`; set it only when the configured
model accepts an explicit temperature.

## 9. Install systemd Service

```bash
sudo cp /opt/soteria/infra/soteria.service /etc/systemd/system/soteria.service
sudo systemctl daemon-reload
sudo systemctl enable soteria
sudo systemctl restart soteria
sudo systemctl status soteria --no-pager
```

Check application logs:

```bash
sudo journalctl -u soteria -f
```

## 10. Configure Caddy

```bash
sudo cp /opt/soteria/infra/Caddyfile.production /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable caddy
sudo systemctl reload caddy || sudo systemctl restart caddy
sudo systemctl status caddy --no-pager
```

Caddy automatically obtains Let's Encrypt certificates and redirects HTTP to HTTPS for site labels with hostnames. Do not add Certbot.

## 11. Public Static Red-Flag Pages

H1-7a expects `/policies/...` pages to be served by Caddy from `/var/www/soteria-public-pages`.

Current repo state: no committed static HTML public pages are present under `public/`, `policies/`, or another HTML output directory. When those pages are available, copy them into `/var/www/soteria-public-pages/policies/` as directory-index pages, for example:

```bash
sudo mkdir -p /var/www/soteria-public-pages/policies/star-super-star
sudo cp /opt/soteria/PATH_TO_COMMITTED_PUBLIC_PAGE.html /var/www/soteria-public-pages/policies/star-super-star/index.html
sudo chown -R root:root /var/www/soteria-public-pages
sudo find /var/www/soteria-public-pages -type d -exec chmod 0755 {} \;
sudo find /var/www/soteria-public-pages -type f -exec chmod 0644 {} \;
```

Until at least one static HTML page exists there, `https://soteria.co.in/policies/...` will correctly bypass Python but return a static 404.

## 12. Verification Commands

Run these and paste the actual output into the H1-7a review:

```bash
sudo systemctl status soteria --no-pager
sudo systemctl status caddy --no-pager
curl -I https://soteria.co.in
curl -I https://soteria.co.in/health
curl -I https://www.soteria.co.in
curl -I http://soteria.co.in
curl -I https://soteria.co.in/policies/star-super-star
```

Expected checks:
- `soteria` is `active (running)`.
- `caddy` is `active (running)`.
- `https://soteria.co.in/health` returns `200`.
- `http://soteria.co.in` redirects to HTTPS.
- No `curl -k` or insecure TLS flag is needed.

## 13. End-To-End Upload Check

Create a trivial one-page PDF locally on the VM:

```bash
cd /tmp
python3 - <<'PY'
from pathlib import Path
stream = b"BT\n/F1 12 Tf\n72 720 Td\n(Test policy wording.) Tj\nET"
objects = [
    (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
    (2, b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>"),
    (3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    (4, b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 3 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>"),
    (5, b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"),
]
pdf = b"%PDF-1.4\n"
offsets = {}
for number, body in objects:
    offsets[number] = len(pdf)
    pdf += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
startxref = len(pdf)
pdf += b"xref\n0 6\n0000000000 65535 f \n"
for number in range(1, 6):
    pdf += f"{offsets[number]:010d} 00000 n \n".encode("ascii")
pdf += f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode("ascii")
Path("soteria-smoke.pdf").write_bytes(pdf)
PY
```

Upload it and follow the result URL:

```bash
curl -i -X POST https://soteria.co.in/upload \
  -F "policy_pdf=@/tmp/soteria-smoke.pdf;type=application/pdf"
```

Copy the `Location: /a/<session_token>` value, then poll:

```bash
curl -L https://soteria.co.in/a/<SESSION_TOKEN>
```

Record the actual Anthropic API cost incurred for this smoke test in `PROGRESS.md`.

## 14. Restart After Future Code Pulls

```bash
cd /opt/soteria
git pull --ff-only origin main
cd /opt/soteria/backend
.venv/bin/python -m pip install -e .
sudo systemctl restart soteria
sudo systemctl status soteria --no-pager
```
