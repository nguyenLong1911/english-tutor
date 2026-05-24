# Deploy A20 App to Google Cloud Compute Engine

This guide deploys the current app to one Google Cloud Compute Engine VM using Docker Compose.

The app will run these containers:

- `frontend` on port `5173`
- `backend` on port `8000`
- `postgres`
- `redis`
- `qdrant`

For a first deployment, open the web app at:

```text
http://YOUR_VM_EXTERNAL_IP:5173
```

## 0. What You Need Before Starting

You need:

1. A Google account.
2. A Google Cloud project with billing enabled.
3. This repository pushed to GitHub, GitLab, or another Git server.
4. Basic access to the Google Cloud Console.

If your code is not pushed anywhere yet, push it first. The VM needs a way to download the code.

## 1. Create Or Select A Google Cloud Project

1. Open the Google Cloud Console: <https://console.cloud.google.com/>
2. At the top of the page, click the project selector.
3. Click **New Project**, or select an existing project.
4. Make sure billing is enabled for the project.
5. In the search bar, search for **Compute Engine API**.
6. Open it and click **Enable** if it is not enabled yet.

## 2. Create A Compute Engine VM

1. In Google Cloud Console, search for **Compute Engine**.
2. Open **Compute Engine > VM instances**.
3. Click **Create instance**.
4. Use these beginner-friendly settings in the **Machine configuration** section:

```text
Name: a20-app-vm
Region: choose the region closest to your users
Zone: any zone in that region
Machine type: e2-standard-2
```

5. Find the **OS and Storage** section.
6. Next to the boot disk, click **Change**.
7. On the **Public images** tab, choose:

```text
Operating system: Ubuntu
Version: Ubuntu 24.04 LTS
Boot disk type: Balanced persistent disk
Size: 30 GB
```

8. Click **Select**.
9. Find the **Networking** section.
10. Find the **Firewall** area.
11. Check **Allow HTTP traffic**.

Notes:

- `e2-standard-2` gives 2 vCPU and 8 GB RAM. This is safer for the full Docker Compose stack because Qdrant, Postgres, Redis, backend, and frontend all run on the same VM.
- `Allow HTTP traffic` opens port `80`, but this app currently runs on port `5173`, so you still need the custom firewall rule in the next step.
- If you do not see **Allow HTTP traffic**, it is usually inside **Networking > Firewall** on the left side of the VM creation form.

12. Click **Create**.
13. Wait until the VM shows a green check mark.

## 3. Create A Firewall Rule For The Frontend

The frontend container listens on port `5173`.

1. In Google Cloud Console, go to **VPC network > Firewall**.
2. Click **Create firewall rule**.
3. Fill in:

```text
Name: allow-a20-frontend-5173
Network: default
Direction of traffic: Ingress
Action on match: Allow
Targets: All instances in the network
Source IPv4 ranges: 0.0.0.0/0
Protocols and ports: tcp:5173
```

4. Click **Create**.

Optional for testing the backend Swagger docs:

Create another firewall rule for `tcp:8000`. If possible, set **Source IPv4 ranges** to your own IP address instead of `0.0.0.0/0`.

Do not create public firewall rules for:

```text
5432
6379
6333
```

Those are Postgres, Redis, and Qdrant ports. Keep them private.

## 4. SSH Into The VM

1. Go to **Compute Engine > VM instances**.
2. Find `a20-app-vm`.
3. Click **SSH**.
4. A browser terminal will open.

All commands below are run inside that SSH terminal.

## 5. Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
```

## 6. Install Git And Nano

```bash
sudo apt install -y git nano
```

`git` downloads your private repository. `nano` is a beginner-friendly terminal editor for editing `.env`.

Check Git:

```bash
git --version
```

## 7. Install Docker And Docker Compose

Run these commands on the VM:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Check Docker:

```bash
sudo docker run hello-world
docker compose version
```

Allow your SSH user to run Docker without typing `sudo` every time:

```bash
sudo usermod -aG docker $USER
```

Close the SSH tab, open SSH again, then check:

```bash
docker ps
```

If `docker ps` works without an error, Docker is ready.

## 8. Login To GitHub From The VM

If your repository is private, set up SSH access before cloning the code.

Run these commands inside the VM SSH terminal.

Set your Git identity:

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Create an SSH key on the VM:

```bash
ssh-keygen -t ed25519 -C "your-email@example.com"
```

When it asks where to save the key, press `Enter`.

When it asks for a passphrase, you can press `Enter` twice to leave it empty for a simple deployment VM.

Show the public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the full output. It starts with:

```text
ssh-ed25519 ...
```

Add the key to GitHub:

1. Open <https://github.com/settings/keys>
2. Click **New SSH key**.
3. Title: `GCP A20 VM`.
4. Key type: `Authentication Key`.
5. Paste the public key from the VM.
6. Click **Add SSH key**.

Test the SSH connection:

```bash
ssh -T git@github.com
```

The first time, GitHub may ask:

```text
Are you sure you want to continue connecting?
```

Type:

```text
yes
```

If it works, GitHub will print a message like:

```text
Hi YOUR_USERNAME! You've successfully authenticated...
```

## 9. Download The Project Code

Replace the URL below with your real Git repository URL:

```bash
git clone git@github.com:YOUR_USERNAME/A20-App-134.git
cd A20-App-134
```

If the repository is inside a GitHub organization, use:

```bash
git clone git@github.com:ORG_NAME/A20-App-134.git
cd A20-App-134
```

## 10. Create The Production `.env` File

The Docker Compose file lives in `src`, so the `.env` file must also be inside `src`.

```bash
cd ~/A20-App-134/src
cp .env.example .env
nano .env
```

If `nano` says `command not found`, install it:

```bash
sudo apt update
sudo apt install -y nano
nano .env
```

Alternative without installing nano:

```bash
vi .env
```

For `vi`, press `i` to edit, press `Esc` when done, type `:wq`, then press `Enter`.

Change these values:

```text
POSTGRES_USER=a20_user
POSTGRES_PASSWORD=CHANGE_THIS_TO_A_LONG_RANDOM_PASSWORD
POSTGRES_DB=a20_prod

JWT_SECRET=CHANGE_THIS_TO_A_LONG_RANDOM_SECRET
FRONTEND_ORIGIN=http://YOUR_VM_EXTERNAL_IP:5173
EMAIL_RESET_BASE_URL=http://YOUR_VM_EXTERNAL_IP:5173/auth/reset

COOKIE_SECURE=false
COOKIE_SAMESITE=lax
SENTRY_ENVIRONMENT=production
LOG_LEVEL=INFO
```

If you have API keys, also fill in:

```text
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GROQ_API_KEY=
RESEND_API_KEY=
```

Generate a strong `JWT_SECRET` with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Important:

- Replace `YOUR_VM_EXTERNAL_IP` with the VM external IP from the Compute Engine VM list.
- Keep `COOKIE_SECURE=false` while using plain `http`.
- Use `COOKIE_SECURE=true` only after you set up HTTPS.

Save in nano:

1. Press `Ctrl + O`.
2. Press `Enter`.
3. Press `Ctrl + X`.

## 11. Start The App

Make sure you are in the `src` folder:

```bash
pwd
```

The output should end with:

```text
A20-App-134/src
```

Start everything:

```bash
docker compose up -d --build
```

Check containers:

```bash
docker compose ps
```

Wait until `backend`, `postgres`, `redis`, and `qdrant` are healthy or running.

## 12. Seed The Vocabulary Data

The backend container already runs database migrations on startup. After the stack is up, seed vocabulary:

```bash
docker compose exec backend python -m app.scripts.seed_vocabulary
```

## 13. Test The Deployment

In the VM SSH terminal:

```bash
curl http://localhost:8000/health
```

Expected result:

```json
{"ok":true}
```

From your browser:

```text
http://YOUR_VM_EXTERNAL_IP:5173
```

If you opened backend port `8000`, you can also test:

```text
http://YOUR_VM_EXTERNAL_IP:8000/docs
```

## 14. Common Commands

Run these from the `src` folder.

See container status:

```bash
docker compose ps
```

See logs for all containers:

```bash
docker compose logs -f
```

See backend logs only:

```bash
docker compose logs -f backend
```

Restart the app:

```bash
docker compose restart
```

Stop the app:

```bash
docker compose down
```

Stop the app and delete database volumes:

```bash
docker compose down -v
```

Only use `docker compose down -v` if you are okay deleting local Postgres and Qdrant data on the VM.

## 15. Deploy New Code Later

When you update the code and push it to Git, SSH into the VM and run:

```bash
cd ~/A20-App-134
git pull
cd src
docker compose up -d --build
docker compose exec backend python -m app.scripts.seed_vocabulary
```

Check the app again:

```bash
docker compose ps
curl http://localhost:8000/health
```

## 16. Troubleshooting

### The Browser Cannot Open The Site

Check:

1. The VM is running.
2. The external IP is correct.
3. The firewall rule allows `tcp:5173`.
4. The frontend container is running:

```bash
cd ~/A20-App-134/src
docker compose ps
docker compose logs -f frontend
```

### Backend Is Unhealthy

Check backend logs:

```bash
docker compose logs -f backend
```

Common causes:

- `.env` is missing.
- `POSTGRES_PASSWORD` or `DATABASE_URL` values do not match.
- Postgres is still starting.
- The vocabulary CSV file is missing from `data/vocabulary/vocabulary_v1.csv`.

### Login Or Cookies Do Not Work

Check `.env`:

```text
FRONTEND_ORIGIN=http://YOUR_VM_EXTERNAL_IP:5173
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

Then restart:

```bash
docker compose restart backend
```

### Docker Says Permission Denied

Run:

```bash
sudo usermod -aG docker $USER
```

Then close SSH and open it again.

### The VM Is Too Slow

Stop the VM and change the machine type to a larger one, such as:

```text
e2-standard-4
```

Then start the VM again.

## 17. Important Production Notes

This guide uses the current repository Docker setup. It is good for a first VM deployment or demo.

Before using it for real users, improve these items:

1. Add HTTPS with a domain name.
2. Serve the frontend as a production build instead of the Vite dev server.
3. Stop exposing backend port `8000` publicly unless you need it.
4. Move Postgres to Cloud SQL if you need managed backups and easier operations.
5. Add VM disk snapshots or database backups.
6. Store secrets in Secret Manager instead of a plain `.env` file.

## 18. Clean Up To Avoid Charges

If you are finished testing:

1. Go to **Compute Engine > VM instances**.
2. Select `a20-app-vm`.
3. Click **Stop** to pause compute charges.
4. Click **Delete** if you no longer need it.

Also check:

- **VPC network > IP addresses** for unused static IPs.
- **Disks** for unattached persistent disks.
- **Snapshots** if you created any.

## References

- Google Cloud: Create a Linux VM instance in Compute Engine: <https://cloud.google.com/compute/docs/create-linux-vm-instance>
- Google Cloud: Use VPC firewall rules: <https://cloud.google.com/firewall/docs/using-firewalls>
- Google Cloud: Configure static external IP addresses: <https://cloud.google.com/compute/docs/ip-addresses/configure-static-external-ip-address>
- GitHub: Generate a new SSH key and add it to the ssh-agent: <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent>
- GitHub: Add a new SSH key to your GitHub account: <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account>
- Docker: Install Docker Engine on Ubuntu: <https://docs.docker.com/engine/install/ubuntu/>
