# Flask Docker App: Multi-Stage Build

A minimal Flask application containerized with a production-ready, multi-stage Dockerfile. The image is built and published to Docker Hub automatically through GitHub Actions whenever a semantic version tag is pushed.

- **Docker Hub:** https://hub.docker.com/r/bluezapus/app-healthy
- **Current version:** `v1.0.0`

---

## Project Structure

```
.
├── app.py                      # Flask application
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Multi-stage build
├── .dockerignore               # Files excluded from build context
├── Dockerfile.naive            # Unoptimized baseline (for size comparison)
└── .github/workflows/
    └── docker.yml              # CI: build and push on Git tag
```

## Endpoints

| Route     | Description                                          |
| --------- | ---------------------------------------------------- |
| `/`       | Returns a JSON greeting and the `APP_ENV`            |
| `/health` | Returns `{"status": "healthy"}`, used by HEALTHCHECK |

---

## Quick Start

### Run the published image

```bash
docker pull bluezapus/app-healthy:v1.0.0
docker run -d --name flask-app -p 5000:5000 bluezapus/app-healthy:v1.0.0

curl http://localhost:8080/
curl http://localhost:8080/health
```

### Build locally

```bash
docker build -t app-healthy:v1.0.0 .
docker run -d --name app-healthy -p 8080:8080 app-healthy:v1.0.0
```

### Build with a custom environment (build argument)

```bash
docker build --build-arg APP_ENV=staging -t app-healthy:staging .
docker run --rm -p 8080:8080 app-healthy:staging
```

---

## Build Choices and Justification

### 1. Base image: `python:3.12-slim`

|Image|Approx. size|Notes|
|---|---|---|
|`python:3.12`|~1 GB|Includes many unused tools, larger attack surface|
|`python:3.12-slim`|~130 MB|Debian-based, small, compatible with nearly all Python packages|
|`python:3.12-alpine`|~50 MB|Smallest, but uses musl libc; wheels often unavailable, slower builds|

**Decision:** `slim` offers the best balance between size and compatibility. Alpine saves a few extra megabytes but can cause build failures and subtle runtime issues with packages that rely on glibc.

### 2. Multi-stage build

- **Stage 1 (builder):** creates a virtual environment and installs dependencies.
- **Stage 2 (runtime):** copies only the finished virtual environment and the application code.

Build-time tooling and pip caches never reach the final image, which keeps it smaller and reduces the attack surface.

### 3. Non-root user and WORKDIR

- A dedicated system user `app` is created and the container runs with `USER app`. If the application is compromised, the attacker does not get root inside the container.
- `WORKDIR /app` provides a predictable location for the application code.

### 4. Layer caching

`requirements.txt` is copied and installed **before** the application code. When only the code changes, Docker reuses the cached dependency layer, so rebuilds are much faster.

### 5. `.dockerignore`

Excludes `.git`, virtual environments, `__pycache__`, `.env`, editor folders, and documentation. This speeds up builds, shrinks the context, and prevents secrets from leaking into the image.

### 6. HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=2)" || exit 1
```

Docker polls `/health` every 30 seconds. The slim image has no `curl`, so the check uses Python's standard library instead of installing extra packages. After 3 consecutive failures the container is marked `unhealthy`.

### 7. Production server

The image runs **Gunicorn** instead of Flask's built-in development server, which is not intended for production use.

### 8. Build argument

`ARG APP_ENV` (default `production`) is exposed as an environment variable so the same Dockerfile can produce differently configured images.

### 9. Environment variables

`PYTHONDONTWRITEBYTECODE=1` avoids writing `.pyc` files, and `PYTHONUNBUFFERED=1` makes logs appear immediately in `docker logs`.

---

## Results

### Image size comparison

|Version|Image|Disk usage|Content size (compressed)|
|---|---|---|---|
|Naive (`python:3.12`, single-stage)|`app-healthy:naive`|_fill in_ MB|_fill in_ MB|
|Optimized (`slim`, multi-stage, non-root)|`app-healthy:v1.0.0`|~205 MB|~49.5 MB|

Measured with:

```bash
docker images | grep app-healthy
```

### Verification

```bash
docker ps                       # STATUS shows "(healthy)" after ~30s
docker exec flask-app whoami    # prints: app
```

---

## CI/CD: Automated Semantic Versioning

The workflow in `.github/workflows/docker.yml` runs whenever a tag matching `v*.*.*` is pushed. It logs in to Docker Hub, derives image tags from the Git tag, then builds and pushes the image.

Pushing the tag `v1.0.0` produces the Docker tags:

- `bluezapus/app-healthy:v1.0.0`
- `bluezapus/app-healthy:v1.0`

### Required GitHub secrets

Set these under **Settings → Secrets and variables → Actions → Repository secrets**:

|Name|Value|
|---|---|
|`DOCKERHUB_USERNAME`|Your Docker Hub username|
|`DOCKERHUB_TOKEN`|A Docker Hub access token with Read & Write access|

### Releasing a new version

```bash
git tag v1.0.1
git push origin v1.0.1
```

---

## Troubleshooting Notes

Problems encountered during development and how they were solved.

|Problem|Cause|Fix|
|---|---|---|
|`Temporary failure in name resolution` during `docker build` / `docker push`|DNS on the host was unreliable|Set DNS servers (`8.8.8.8`, `1.1.1.1`) for the system and in `/etc/docker/daemon.json`, then restart Docker|
|`timeout awaiting response headers` on `docker push`|Unstable connection to Docker Hub|Retried the push (completed layers are not re-uploaded), limited `max-concurrent-uploads` to 1|
|GitHub Actions workflow showed 0 runs|Workflow only triggers on tags, and a tag points to a specific commit|Pushed a `v*.*.*` tag on a commit that contains the workflow file|
|`Username and password required` in `docker/login-action`|Secrets were empty: a secret had been created with the wrong **Name** (the username was typed into the name field)|Recreated `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` with the correct names and values|
|Deprecation warning about `punycode`|Node.js warning inside the GitHub Action|Harmless, can be ignored|

---

## Tech Stack

- Python 3.12, Flask, Gunicorn
- Docker (multi-stage build)
- GitHub Actions
- Docker Hub
