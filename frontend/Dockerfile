FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine

WORKDIR /app

RUN npm install -g http-server

COPY --from=builder /app/dist ./dist

USER node

EXPOSE 5173

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:5173/ || exit 1

CMD ["http-server", "dist", "-p", "5173", "-c-1"]
