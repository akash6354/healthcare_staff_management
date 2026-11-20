# Builds both React apps and serves them with Caddy. Build from the repo root:
#   docker build -f infra/web/Dockerfile -t oglos-web:local .
FROM node:22.12-alpine AS build
WORKDIR /repo
RUN npm install -g pnpm@10.34.9  # not corepack: old Node images ship stale npm signing keys
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json eslint.config.js ./
COPY apps/staff-pwa/package.json apps/staff-pwa/
COPY apps/web-admin/package.json apps/web-admin/
COPY packages/ui/package.json packages/ui/
COPY packages/i18n/package.json packages/i18n/
COPY packages/client/package.json packages/client/
RUN pnpm install --frozen-lockfile
COPY media media
COPY scripts scripts
COPY packages packages
COPY apps/staff-pwa apps/staff-pwa
COPY apps/web-admin apps/web-admin
RUN pnpm --filter @oglos/staff-pwa build && pnpm --filter @oglos/web-admin build

FROM caddy:2.8.4-alpine
COPY infra/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /repo/apps/web-admin/dist /srv/admin
COPY --from=build /repo/apps/staff-pwa/dist /srv/staff
