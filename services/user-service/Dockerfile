FROM python:3.13-slim

# Build context: repo root.
# Mirror the repo layout inside the image so the relative paths for cf-auth
# and cf-keycloak (`../../packages/*` in pyproject.toml) resolve the same as
# on disk.

RUN pip install --no-cache-dir uv

COPY packages/auth /packages/auth
COPY packages/keycloak /packages/keycloak
COPY services/user-service/pyproject.toml /services/user-service/pyproject.toml

WORKDIR /services/user-service
RUN uv pip install --system --no-cache -r pyproject.toml

COPY services/user-service/app ./app

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
