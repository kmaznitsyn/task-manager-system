FROM python:3.13-slim

# Build context: repo root.
# Mirror the repo layout inside the image so cf-auth's relative path
# (`../../packages/auth` in pyproject.toml) resolves the same as on disk.

RUN pip install --no-cache-dir uv

COPY packages/auth /packages/auth
COPY services/task-service/pyproject.toml /services/task-service/pyproject.toml

WORKDIR /services/task-service
RUN uv pip install --system --no-cache -r pyproject.toml

COPY services/task-service/app ./app

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
