FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_DEMO_MODE=true
ARG VITE_API_BASE_URL=/api
ARG VITE_TELEGRAM_SUPPORT_URL=https://t.me/VPaNfi_bot
ARG VITE_TELEGRAM_BOT_URL=https://t.me/VPaNfi_bot

ENV VITE_DEMO_MODE=${VITE_DEMO_MODE} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_TELEGRAM_SUPPORT_URL=${VITE_TELEGRAM_SUPPORT_URL} \
    VITE_TELEGRAM_BOT_URL=${VITE_TELEGRAM_BOT_URL}

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
