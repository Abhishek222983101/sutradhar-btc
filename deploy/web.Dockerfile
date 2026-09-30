FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /repo
COPY pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/pnpm-lock.yaml* apps/web/
COPY apps/web apps/web
WORKDIR /repo/apps/web
RUN pnpm install --frozen-lockfile=false && VITE_API_BASE_URL= pnpm build && node scripts/check-no-external-urls.mjs

FROM caddy:2-alpine
COPY --from=build /repo/apps/web/dist /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
