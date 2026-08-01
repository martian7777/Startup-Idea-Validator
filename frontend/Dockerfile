FROM node:22.22.0-alpine3.23 AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22.22.0-alpine3.23 AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE=
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22.22.0-alpine3.23 AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=build --chown=nextjs:nodejs /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
