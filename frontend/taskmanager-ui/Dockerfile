
# Stage 1: build the Angular app
FROM node:20-alpine AS build
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
COPY . .
RUN --mount=type=cache,target=/app/.angular/cache \
    pnpm run build --configuration production

# Stage 2: serve with nginx
FROM nginx:alpine
COPY --from=build /app/dist/taskmanager-ui/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Cloud Run sends traffic to $PORT (default 8080), not 80
ENV PORT=8080
CMD ["sh", "-c", "sed -i \"s/listen 80;/listen ${PORT};/\" /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
