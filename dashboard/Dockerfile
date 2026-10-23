# Next.js frontend: standalone output, served on :3100
#
# Self-hosting alternative to the Cloudflare Worker deploy.
# NEXT_PUBLIC_* values are baked into the JS bundle at build time, so they are
# build args here rather than runtime env. .dockerignore excludes .env* so a
# stale .env.local cannot override them.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_APP_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build && \
    # Next nests standalone output under the workspace path when it detects a
    # repo root above the app. Flatten it so server.js is always at /app.
    if [ ! -f .next/standalone/server.js ]; then \
      S=$(find .next/standalone -name server.js | head -1); \
      cp -r "$(dirname "$S")"/. .next/standalone/ ; \
    fi

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3100 HOSTNAME=0.0.0.0
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3100
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3100/ >/dev/null 2>&1 || exit 1
CMD ["node", "server.js"]
