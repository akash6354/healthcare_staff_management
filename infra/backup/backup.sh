#!/bin/sh
# Nightly encrypted backup (docs/security.md §7): pg_dump → age-encrypt → S3 in a second Indian region.
# Cron on the VM:  15 2 * * *  /opt/oglos/infra/backup/backup.sh >> /var/log/oglos-backup.log 2>&1
# Needs: docker, age (BSD-3), aws CLI with a role/credentials limited to the backup bucket.
# Env (from /opt/oglos/.env.production): BACKUP_BUCKET, BACKUP_REGION (ap-south-2), AGE_RECIPIENT (public key).
set -eu
cd "$(dirname "$0")/../.."
. ./.env.production

stamp=$(date -u +%Y%m%dT%H%M%SZ)
file="oglos-${stamp}.dump.age"
docker compose -f infra/docker-compose.prod.yml exec -T postgres \
  pg_dump -U postgres -d oglos --format=custom --no-owner \
  | age -r "$AGE_RECIPIENT" > "/tmp/${file}"
aws s3 cp "/tmp/${file}" "s3://${BACKUP_BUCKET}/db/${file}" --region "$BACKUP_REGION" --sse AES256
rm -f "/tmp/${file}"
echo "$(date -u +%FT%TZ) backup ok ${file}"
# Retention: the bucket has a 30-day lifecycle rule (set once, see docs/deploy.md).
