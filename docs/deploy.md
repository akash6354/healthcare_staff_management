# Production deployment (AWS Mumbai, one VM)

Target: Olympus pilot handover. About an hour once the AWS account and DNS exist.
Everything stays in India: VM, database, photos (ap-south-1), backups (ap-south-2).

## 0. What you need
- AWS account with billing, region **ap-south-1 (Mumbai)**.
- DNS control for `oglos.site`.
- A shared password manager for the generated secrets (never in git or chat).

## 1. AWS resources (console, once)
| Resource | Setting |
|---|---|
| **Lightsail instance** (or EC2 t3.medium) | Ubuntu 24.04 LTS, 2 vCPU / 4 GB (enough for the pilot), static IP, ap-south-1 |
| Firewall | inbound **22 (your IP only), 80, 443**. Nothing else |
| **S3 bucket** `oglos-evidence-prod` | ap-south-1, **Block all public access ON**, SSE-S3 encryption, versioning off |
| **S3 bucket** `oglos-backups` | **ap-south-2 (Hyderabad)**, block public access, lifecycle rule: expire after 30 days |
| **SES** | verify domain `oglos.site` (DKIM records in DNS), request production access (leaves the sandbox) |
| **IAM role/user** for the VM | allow only: `s3:GetObject/PutObject/DeleteObject/ListBucket` on the evidence bucket, `s3:PutObject/GetObject/ListBucket` on the backup bucket, `ses:SendEmail` |

On Lightsail, attach credentials via an IAM user restricted to the policy above and put the keys in
`~/.aws/credentials` for the backup script only; the app reads `S3_ACCESS_KEY`/`S3_SECRET_KEY` from `.env.production`
(leave them empty on EC2 with an instance role).

## 2. DNS
```
app.oglos.site   A   <static IP>     # admin, supervisor, MD
ops.oglos.site   A   <static IP>     # staff phone app
```
Plus the SES DKIM CNAMEs and an SPF/DMARC record for `oglos.site`.

## 3. Server hardening (once)
```bash
sudo adduser --disabled-password oglos && sudo usermod -aG docker oglos
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/; s/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 fail2ban unattended-upgrades age awscli
sudo dpkg-reconfigure -plow unattended-upgrades
timedatectl status          # NTP must say "synchronized: yes" (CERT-In clock sync); AWS Time Sync is the default
```

## 4. Install OGLOS
```bash
sudo mkdir -p /opt/oglos && sudo chown oglos /opt/oglos && cd /opt/oglos
git clone https://github.com/akash6354/healthcare_staff_management.git .
cp .env.production.example .env.production && chmod 600 .env.production
# fill every REPLACE value (secrets: see the generator commands at the top of the file)

docker build -t oglos-api:local apps/api
docker build -f infra/web/Dockerfile -t oglos-web:local .
docker compose -f infra/docker-compose.prod.yml --env-file .env.production up -d
docker compose -f infra/docker-compose.prod.yml ps        # all healthy; "migrate" exited 0
curl -sS https://app.oglos.site/api/v1/health            # {"status":"ok"}
```
Caddy obtains HTTPS certificates automatically on first request.

## 5. Create the hospital
```bash
docker compose -f infra/docker-compose.prod.yml run --rm api \
  python -m app.modules.platform.cli create-hospital \
  --code OLYMPUS --name "Olympus Hospital" --city Bengaluru \
  --admin-email <olympus-admin-email> --admin-name "<admin name>"
```
It prints a one-time password. The admin signs in at `https://app.oglos.site` (hospital code `OLYMPUS`), enrols
two-step sign-in, then sets up branch, floors, desks, staff, roster and daily tasks under **Setup**.
Publish the hospital's own staff notice if it differs from the default (contact details!).

## 6. Backups and checks
```bash
crontab -e
15 2 * * *  /opt/oglos/infra/backup/backup.sh >> /var/log/oglos-backup.log 2>&1
```
- Keep the **age private key offline** (password manager). Only the public key is on the server.
- Monthly: `infra/backup/restore-drill.sh <identity-file>`; record the result.
- Nightly jobs run inside `beat`: retention (02:00 IST) and audit-chain verification (03:00 IST).

## 7. Logs (CERT-In: 180 days, in India)
Container logs are buffered locally (json-file, ~2 GB per service). Before go-live, ship them to
**CloudWatch Logs in ap-south-1** with retention set to **180 days** (Docker `awslogs` driver, or the
CloudWatch agent). Logs contain no names, phones, emails or codes (scrubbed in the API).

## 8. Updates
```bash
cd /opt/oglos && git pull
docker build -t oglos-api:local apps/api && docker build -f infra/web/Dockerfile -t oglos-web:local .
docker compose -f infra/docker-compose.prod.yml --env-file .env.production up -d   # migrate runs first
```

## Pilot exit (product plan section 5)
At the end of the 14 days, either move to the paid plan or export and delete: the OGLOS super-admin exports
everything (`/privacy/users/{id}/export` per person today; the one-click ZIP export is on the roadmap), the hospital
confirms, then drop the hospital's data and photos. Contract promise: export within 7 days of request.
