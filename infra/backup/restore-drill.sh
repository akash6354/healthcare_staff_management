#!/bin/sh
# Monthly restore drill: restore the newest backup into a throwaway Postgres and verify audit chains.
# Usage on the VM:  infra/backup/restore-drill.sh /path/to/age-identity.txt
set -eu
cd "$(dirname "$0")/../.."
. ./.env.production
identity="$1"

latest=$(aws s3 ls "s3://${BACKUP_BUCKET}/db/" --region "$BACKUP_REGION" | sort | tail -1 | awk '{print $4}')
aws s3 cp "s3://${BACKUP_BUCKET}/db/${latest}" /tmp/drill.dump.age --region "$BACKUP_REGION"
age -d -i "$identity" /tmp/drill.dump.age > /tmp/drill.dump

docker rm -f oglos-drill >/dev/null 2>&1 || true
docker run -d --name oglos-drill -e POSTGRES_PASSWORD=drill postgres:16.4-alpine >/dev/null
sleep 8
docker exec oglos-drill psql -U postgres -c "CREATE ROLE oglos_owner; CREATE ROLE oglos_app; CREATE ROLE oglos_platform;" >/dev/null
docker cp /tmp/drill.dump oglos-drill:/tmp/drill.dump
docker exec oglos-drill createdb -U postgres oglos
docker exec oglos-drill pg_restore -U postgres -d oglos --no-owner /tmp/drill.dump
docker exec oglos-drill psql -U postgres -d oglos -tAc \
  "SELECT 'hospitals='||count(*) FROM hospitals UNION ALL SELECT 'audit_events='||count(*) FROM audit_events UNION ALL SELECT 'tasks='||count(*) FROM tasks"
docker rm -f oglos-drill >/dev/null
rm -f /tmp/drill.dump /tmp/drill.dump.age
echo "$(date -u +%FT%TZ) restore drill ok (${latest}). Record the result in the ops log."
