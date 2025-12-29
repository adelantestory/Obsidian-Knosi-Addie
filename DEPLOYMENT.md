# Knosi Server Deployment Guide

Step-by-step guide to deploy Knosi on a VPS (tested on Vultr with Ubuntu).

---

## Prerequisites

- Ubuntu 22.04 or later VPS
- Block storage device attached to your VPS (optional but recommended)
- SSH access to your server
- Domain name (optional, for HTTPS)

---

## Step 1: Initial Server Setup

```bash
# SSH into your server
ssh root@your-server-ip

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y git docker.io docker-compose curl

# Enable Docker to start on boot
sudo systemctl enable docker
sudo systemctl start docker

# Verify Docker is running
sudo docker --version
sudo docker compose version
```

---

## Step 2: Setup Block Storage (Optional but Recommended)

This step configures persistent storage for your PostgreSQL database.

```bash
# List available block devices
lsblk

# You should see your block device (e.g., vdb, sdb, etc.)
# Example output:
# NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
# vda    252:0    0   25G  0 disk
# └─vda1 252:1    0   25G  0 part /
# vdb    252:16   0  100G  0 disk          <-- This is your block storage

# Format the block device (ONLY IF NEW - THIS ERASES DATA!)
sudo mkfs.ext4 /dev/vdb

# Create mount point
sudo mkdir -p /mnt/knosi-data

# Get the UUID of your block device
sudo blkid /dev/vdb

# Copy the UUID from the output (looks like: UUID="abc123-...")

# Edit fstab for auto-mount on reboot
sudo nano /etc/fstab

# Add this line at the end (replace with YOUR UUID from above):
UUID=your-uuid-here  /mnt/knosi-data  ext4  defaults,nofail  0  2

# Save and exit (Ctrl+X, then Y, then Enter)

# Mount the device
sudo mount -a

# Verify it mounted successfully
df -h | grep knosi-data
```

---

## Step 3: Clone and Configure Knosi

```bash
# Navigate to home directory
cd ~

# Clone the repository
git clone https://github.com/yourusername/knosi.git
cd knosi/server

# Create .env file from example
cp .env.example .env

# Edit the configuration
nano .env
```

**Edit these values in `.env`:**

```bash
# REQUIRED: Your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here

# REQUIRED: Strong PostgreSQL password
POSTGRES_PASSWORD=your-strong-password-here

# REQUIRED: Strong API key for client authentication
API_SECRET_KEY=your-random-secret-key-here

# Optional: File size limit (default 100MB)
MAX_FILE_SIZE_MB=100

# Optional: If using block storage (recommended)
POSTGRES_DATA_PATH=/mnt/knosi-data

# Optional: Custom ports (defaults shown)
API_PORT=48550
WEB_PORT=48080
```

**Save and exit** (Ctrl+X, then Y, then Enter)

---

## Step 4: Start Knosi Services

```bash
# Make sure you're in the server directory
cd ~/knosi/server

# Pull images and build containers
sudo docker-compose build

# Start services in detached mode
sudo docker-compose up -d

# Check container status
sudo docker-compose ps

# You should see 3 containers: knosi-db, knosi-api, knosi-web
# All should show "Up" status

# View logs to verify startup
sudo docker-compose logs -f

# Press Ctrl+C to exit logs when you see:
# "Knosi API started - https://knosi.ai"
# "Embedding model loaded"

# If using block storage, verify PostgreSQL set correct permissions
ls -ln /mnt/knosi-data
# You should see UID 999 (postgres user in container)
# If you see permission errors in logs, run:
# sudo chown -R 999:999 /mnt/knosi-data
# sudo docker-compose restart db
```

---

## Step 5: Verify Services Are Running

```bash
# Check API health
curl http://localhost:48550/api/status

# You should see:
# {"status":"ok","document_count":0,"chunk_count":0}

# Check web server
curl http://localhost:48080

# You should see HTML content
```

---

## Step 6: Configure Docker to Auto-Start Containers

Docker containers with `restart: unless-stopped` will automatically restart on server reboot.

```bash
# Verify restart policy is set
sudo docker inspect knosi-api | grep -A 5 RestartPolicy

# You should see: "Name": "unless-stopped"

# Test by rebooting (optional)
sudo reboot

# After reboot, SSH back in and check
ssh root@your-server-ip
sudo docker-compose -f ~/knosi/server/docker-compose.yml ps

# All containers should be running
```

---

## Step 7: Configure Firewall

```bash
# Allow SSH (if not already configured)
sudo ufw allow 22/tcp

# Allow API port
sudo ufw allow 48550/tcp

# Allow Web port
sudo ufw allow 48080/tcp

# If using HTTPS/reverse proxy
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## Step 8: Test from Your Local Machine

```bash
# From your local computer (not the server)

# Test API
curl http://your-server-ip:48550/api/status

# Test Web UI - open in browser:
http://your-server-ip:48080
```

You should see the Knosi web interface!

---

## Step 9: (Optional) Setup HTTPS with Nginx Reverse Proxy

For production use, you should use HTTPS:

```bash
# Install Nginx and Certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Create Nginx config
sudo nano /etc/nginx/sites-available/knosi

# Add this configuration (replace your-domain.com):
```

```nginx
server {
    server_name your-domain.com;

    # Web UI
    location / {
        proxy_pass http://localhost:48080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API
    location /api {
        proxy_pass http://localhost:48550;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 100M;  # Match MAX_FILE_SIZE_MB
    }
}
```

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/knosi /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Follow prompts, select "Redirect HTTP to HTTPS"
```

---

## Useful Commands

```bash
# View logs
sudo docker-compose -f ~/knosi/server/docker-compose.yml logs -f

# View logs for specific service
sudo docker-compose -f ~/knosi/server/docker-compose.yml logs -f api

# Restart services
sudo docker-compose -f ~/knosi/server/docker-compose.yml restart

# Stop services
sudo docker-compose -f ~/knosi/server/docker-compose.yml down

# Stop and remove volumes (DELETES DATABASE!)
sudo docker-compose -f ~/knosi/server/docker-compose.yml down -v

# Update to latest version
cd ~/knosi
git pull
cd server
sudo docker-compose build
sudo docker-compose up -d

# Check disk usage
df -h
sudo docker system df

# Backup database (if using block storage)
sudo tar -czf knosi-backup-$(date +%Y%m%d).tar.gz /mnt/knosi-data

# Backup database (if using Docker volume)
sudo docker-compose exec db pg_dump -U knosi knosi > knosi-backup-$(date +%Y%m%d).sql
```

---

## Troubleshooting

### Containers won't start
```bash
# Check logs
sudo docker-compose logs

# Common issues:
# - Missing ANTHROPIC_API_KEY in .env
# - Wrong POSTGRES_PASSWORD
# - Port conflicts (check with: sudo netstat -tulpn | grep 48550)
```

### Database issues
```bash
# Check PostgreSQL logs
sudo docker-compose logs db

# Reset database (WARNING: DELETES ALL DATA)
sudo docker-compose down -v
sudo rm -rf /mnt/knosi-data/*  # If using block storage
sudo docker-compose up -d
```

### Permission errors on block storage
```bash
# Ensure correct ownership
sudo chown -R 999:999 /mnt/knosi-data
sudo chmod 700 /mnt/knosi-data
```

### Can't connect from local machine
```bash
# Check firewall
sudo ufw status

# Check if services are listening
sudo netstat -tulpn | grep 48550
sudo netstat -tulpn | grep 48080
```

---

## Next Steps

Once the server is running:

1. **Install a client** (Obsidian plugin or Python script)
2. **Upload test document** via web UI
3. **Try chatting** with your documents
4. **Set up monitoring** (optional: Uptime Kuma, Netdata)
5. **Configure backups** (database snapshots)

---

## Security Checklist

- ✅ Changed default `POSTGRES_PASSWORD`
- ✅ Changed default `API_SECRET_KEY`
- ✅ Firewall configured with UFW
- ✅ HTTPS enabled (if public-facing)
- ✅ Regular backups configured
- ✅ Keep system updated: `sudo apt update && sudo apt upgrade`
