FROM node:22-alpine AS build

WORKDIR /app

COPY clients/web/package.json clients/web/package-lock.json ./
RUN npm ci

COPY clients/web ./

ARG VITE_BASE_PATH=/mobility/
ARG VITE_API_BASE=/mobility
ENV VITE_BASE_PATH=${VITE_BASE_PATH} \
    VITE_API_BASE=${VITE_API_BASE}

RUN npm run build

FROM nginx:1.28-alpine

COPY infra/docker/web-nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
