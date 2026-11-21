# DevPilot Production Deployment Guide

This document describes how to deploy DevPilot to a production Linux VPS or Cloud Virtual Machine (e.g. AWS EC2, DigitalOcean Droplet, Hetzner, Linode) using Docker Compose and SSL reverse proxy.

---

## 1. Prerequisites

- A Linux server (Ubuntu 22.04 / 24.04 LTS recommended) with at least 2GB RAM.
- A public IPv4 address and registered domain name (e.g., `devpilot.yourdomain.com`).
- Ports `80` (HTTP), `443` (HTTPS), and `5000` (API) accessible in your firewall/security group.
- Docker and Docker Compose installed:
  ```bash
  sudo apt-get update
  sudo apt-get install -y docker.io docker-compose-v2
  sudo systemctl enable --now docker
  ```

---

## 2. Deploy with Docker Compose

1. Clone your DevPilot repository:
   ```bash
   git clone https://github.com/your-org/DevPilot.git /opt/devpilot-platform
   cd /opt/devpilot-platform
   ```

2. Configure environment variables in `.env`:
   ```bash
   cat << 'EOF' > .env
   DEVPILOT_SECRET_KEY=generate-a-strong-random-secret-key-32-chars
   DEVPILOT_ADMIN_PASSWORD=SetAStrongPassword123!
   DEVPILOT_CPU_THRESHOLD=85.0
   DEVPILOT_MEMORY_THRESHOLD=85.0
   DEVPILOT_DISK_THRESHOLD=90.0
   EOF
   ```

3. Launch the complete platform:
   ```bash
   docker compose up -d --build
   ```

4. Verify running containers:
   ```bash
   docker compose ps
   ```
   You should see `devpilot-backend` (port 5000), `devpilot-frontend` (port 80/5173), and `devpilot-ollama` (port 11434).

5. (Optional) Download Ollama's Llama 3.2 model for local AI incident investigations:
   ```bash
   docker exec -it devpilot-ollama ollama pull llama3.2
   ```

---

## 3. HTTPS Configuration with Nginx and Let's Encrypt

Install Certbot for free automated SSL:

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

Configure Nginx reverse proxy at `/etc/nginx/sites-available/devpilot`:

```nginx
server {
    server_name devpilot.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /install.sh {
        proxy_pass http://127.0.0.1:5000/install.sh;
        proxy_set_header Host $host;
    }

    location /agent/ {
        proxy_pass http://127.0.0.1:5000/agent/;
        proxy_set_header Host $host;
    }
}
```

Enable site and acquire certificate:
```bash
sudo ln -s /etc/nginx/sites-available/devpilot /etc/nginx/sites-enabled/
sudo nginx -t
sudo certbot --nginx -d devpilot.yourdomain.com
```

---

## 4. Backups and Maintenance

SQLite data is persistently stored in the `devpilot-data` volume (`/app/backend/devpilot_history.db`).
To take a live consistent backup without stopping the server:

```bash
docker exec devpilot-backend sqlite3 /app/backend/devpilot_history.db ".backup '/app/backend/backup_$(date +%F).db'"
```

