FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL VITE_AUTH0_DOMAIN VITE_AUTH0_CLIENT_ID VITE_AUTH0_AUDIENCE
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Template (não um .conf direto): o entrypoint oficial do nginx roda envsubst nele,
# substituindo ${PORT} pela porta que a plataforma (Railway) definir em runtime.
# Sem isso, o nginx fica sempre fixo na porta 80 e a plataforma pode não achar o container.
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV PORT=80
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null "http://localhost:${PORT}/" || exit 1

CMD ["nginx", "-g", "daemon off;"]
