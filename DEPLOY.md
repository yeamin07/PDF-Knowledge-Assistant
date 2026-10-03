# Deployment Guide: Local → Docker Hub → AWS EC2

> Architecture: Docker Compose on a single EC2 instance. No Nginx. No Kubernetes.
> Two services only: `backend` (FastAPI, port 8000) and `frontend` (Streamlit, port 8501).

---

## 0. One-time Docker Hub setup

```bash
# Replace DOCKERHUB_USER with your actual Docker Hub username.
export DOCKERHUB_USER=your_dockerhub_username
export TAG=1.0.0

docker login                            # prompts for username + password (or PAT)
```

---

## 1. Build & push images from your local machine

```bash
# From the project root (where docker-compose.yml lives):

# Build both images
docker compose --env-file .env build

# Tag them for Docker Hub
docker tag rag-pdf-qa/backend:local  ${DOCKERHUB_USER}/rag-pdf-qa-backend:${TAG}
docker tag rag-pdf-qa/frontend:local ${DOCKERHUB_USER}/rag-pdf-qa-frontend:${TAG}

# Push
docker push ${DOCKERHUB_USER}/rag-pdf-qa-backend:${TAG}
docker push ${DOCKERHUB_USER}/rag-pdf-qa-frontend:${TAG}
```

To publish a new version, bump `TAG` (e.g. `1.0.1`) and re-run.

---

## 2. Launch an Ubuntu EC2 instance

Recommended:
- **AMI**: Ubuntu 22.04 LTS or 24.04 LTS
- **Instance type**: `t3.small` minimum (sentence-transformers needs ~1 GB RAM). `t3.medium` is safer.
- **Storage**: 20 GB gp3
- **Security group inbound rules**:
  - `22`   from your IP (SSH)
  - `8501` from `0.0.0.0/0` (or your IP only) — Streamlit UI
  - (Optional) `8000` from your IP — FastAPI docs
- **Outbound**: allow all (so Docker can pull images and the backend can reach Groq)

---

## 3. One-time host setup on EC2

SSH in, then:

```bash
# Update + install Docker
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify
docker --version
docker compose version

# (Optional) allow your user to run docker without sudo
sudo usermod -aG docker $USER
newgrp docker
```

`docker compose` ships with the `docker-compose-plugin` package on modern Ubuntu, so no separate install is needed.

---

## 4. Deploy the app on EC2

```bash
# Create app directory
sudo mkdir -p /opt/rag-pdf-qa/faiss
sudo chown -R $USER:$USER /opt/rag-pdf-qa

cd /opt/rag-pdf-qa

# Drop the production compose file here
# (scp docker-compose.prod.yml ubuntu@<EC2_IP>:/opt/rag-pdf-qa/docker-compose.yml)

# Create .env with real secrets
cat > .env <<'EOF'
DOCKERHUB_USER=your_dockerhub_username
TAG=1.0.0
CHAT_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=openai/gpt-oss-20b
COLLECTION=pdf_docs
EOF

# Pull images
docker compose --env-file .env pull

# Start
docker compose --env-file .env up -d
```

---

## 5. Day-to-day operations on EC2

```bash
cd /opt/rag-pdf-qa

# Check status
docker compose ps

# Tail logs (both services)
docker compose logs -f

# Logs for one service
docker compose logs -f backend
docker compose logs -f frontend

# Restart a service
docker compose restart backend

# Stop everything
docker compose down

# Stop and DELETE the FAISS volume (wipes all ingested PDFs)
docker compose down -v
```

---

## 6. Updating to a new version

```bash
cd /opt/rag-pdf-qa

# Edit .env: bump TAG=1.0.1
sed -i 's/^TAG=.*/TAG=1.0.1/' .env

# Pull the new image and recreate only the changed containers
docker compose --env-file .env pull
docker compose --env-file .env up -d

# The FAISS volume (/opt/rag-pdf-qa/faiss) is preserved — no re-ingest needed.
```

---

## 7. URLs to hit

| What | URL |
|---|---|
| Streamlit UI (public) | `http://<EC2_PUBLIC_IP>:8501` |
| FastAPI health | `http://<EC2_PUBLIC_IP>:8000/health` |
| FastAPI docs (Swagger) | `http://<EC2_PUBLIC_IP>:8000/docs` |

> Replace `<EC2_PUBLIC_IP>` with the public IPv4 from the EC2 console.
> Tighten the security group to your IP once you've confirmed it works.

---

## 8. Troubleshooting

- **`/ask` returns 404 with "Collection 'pdf_docs' not found"** — that's expected before you upload your first PDF via the UI.
- **Frontend can't reach backend** — `BACKEND_URL` must be `http://backend:8000` (service name), not `localhost`. Check `docker exec rag-frontend env | grep BACKEND_URL`.
- **Out of memory** — sentence-transformers needs ~1 GB just for the model. Bump to `t3.medium` or `t3.large`.
- **Slow first request** — model is pre-baked into the image, but still loaded once on container start; `start_period` in the healthcheck gives it 60s.
