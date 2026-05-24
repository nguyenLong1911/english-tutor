# Connect `a20-app-134.online` To The GCP VM

This guide points the Hostinger domain `a20-app-134.online` to the Google Cloud VM at:

```text
35.200.176.251
```

Use this after the app is already running on the VM from [deploy-google-compute-engine.md](deploy-google-compute-engine.md).

## 1. Check The VM IP

In Google Cloud Console:

1. Open **Compute Engine > VM instances**.
2. Find the VM running the A20 app.
3. Confirm the **External IP** is:

```text
35.200.176.251
```

Important: the domain should point to a static external IP. If this IP is ephemeral, reserve it before relying on the domain.

To reserve the current VM IP in Google Cloud Console:

1. Open **VPC network > IP addresses**.
2. Find `35.200.176.251`.
3. If its type is **Ephemeral**, choose **Reserve static address**.
4. Give it a name such as:

```text
a20-app-static-ip
```

5. Save the reservation.

## 2. Open GCP Firewall Ports

DNS only sends users to the VM. The VM also needs firewall rules that allow web traffic.

For a production domain, open:

```text
tcp:80
tcp:443
```

In Google Cloud Console:

1. Open **VPC network > Firewall**.
2. Click **Create firewall rule**.
3. Create a rule for HTTP:

```text
Name: allow-a20-http
Network: default
Direction of traffic: Ingress
Action on match: Allow
Targets: All instances in the network
Source IPv4 ranges: 0.0.0.0/0
Protocols and ports: tcp:80
```

4. Create a second rule for HTTPS:

```text
Name: allow-a20-https
Network: default
Direction of traffic: Ingress
Action on match: Allow
Targets: All instances in the network
Source IPv4 ranges: 0.0.0.0/0
Protocols and ports: tcp:443
```

Keep database and internal service ports closed to the public internet:

```text
5432
6379
6333
5050
```

## 3. Add DNS Records In Hostinger

If the domain was purchased in Hostinger and still uses Hostinger nameservers, edit DNS in Hostinger hPanel.

1. Log in to Hostinger.
2. Go to **Domains**.
3. Select `a20-app-134.online`.
4. Open **DNS / Nameservers**.
5. Find **DNS records** or **Manage DNS records**.
6. Add or update these records:

```text
Type: A
Name: @
Points to: 35.200.176.251
TTL: default
```

```text
Type: CNAME
Name: www
Points to: a20-app-134.online
TTL: default
```

If Hostinger does not allow the `www` CNAME, use an A record instead:

```text
Type: A
Name: www
Points to: 35.200.176.251
TTL: default
```

Remove or replace old records that point `@` or `www` to another IP address. If there are `AAAA` records for `@` or `www` and the VM does not have IPv6 configured, remove those `AAAA` records so browsers do not try an invalid IPv6 route.

If the domain uses non-Hostinger nameservers, make the same DNS changes in the DNS provider that owns the active nameservers.

## 4. Wait For DNS Propagation

DNS changes are not instant. They often work within minutes, but they can take several hours.

Check from your local machine:

```powershell
Resolve-DnsName a20-app-134.online
Resolve-DnsName www.a20-app-134.online
```

Expected result:

```text
35.200.176.251
```

On Linux or macOS:

```bash
dig +short a20-app-134.online
dig +short www.a20-app-134.online
```

## 5. Quick Test With The Existing App Port

The current Docker Compose setup exposes the frontend on port `5173`.

After DNS resolves, this URL should work if the app is running and the `tcp:5173` firewall rule exists:

```text
http://a20-app-134.online:5173
```

This is useful for testing, but it is not the final production URL because users should not need to type `:5173`.

## 6. Add Nginx For A Clean Domain URL

Use Nginx on the VM to proxy normal web traffic:

- `http://a20-app-134.online` -> frontend container on `localhost:5173`
- `/api/...` -> backend container on `localhost:8000`

SSH into the VM, then install Nginx:

```bash
sudo apt update
sudo apt install -y nginx
```

Create a site config:

```bash
sudo nano /etc/nginx/sites-available/a20-app-134.online
```

Paste:

```nginx
server {
    listen 80;
    server_name a20-app-134.online www.a20-app-134.online;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/a20-app-134.online /etc/nginx/sites-enabled/a20-app-134.online
sudo nginx -t
sudo systemctl reload nginx
```

Now test:

```text
http://a20-app-134.online
```

## 7. Update App Environment For The Domain

On the VM, edit the production `.env` file:

```bash
cd ~/A20-App-134/src
nano .env
```

For HTTP before SSL:

```text
FRONTEND_ORIGIN=http://a20-app-134.online,http://www.a20-app-134.online
EMAIL_RESET_BASE_URL=http://a20-app-134.online/auth/reset
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

Restart the app:

```bash
docker compose up -d --build
```

Also make sure `src/frontend/vite.config.js` allows the domain when the frontend is served by Vite:

```js
server: {
  port: 5173,
  allowedHosts: ['a20-app-134.online', 'www.a20-app-134.online'],
}
```

## 8. Enable HTTPS With Let's Encrypt

After `http://a20-app-134.online` works, install Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Request certificates:

```bash
sudo certbot --nginx -d a20-app-134.online -d www.a20-app-134.online
```

Certbot will update the Nginx config for HTTPS.

Then update `.env` again:

```text
FRONTEND_ORIGIN=https://a20-app-134.online,https://www.a20-app-134.online
EMAIL_RESET_BASE_URL=https://a20-app-134.online/auth/reset
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

Restart:

```bash
docker compose up -d --build
```

Final URLs:

```text
https://a20-app-134.online
https://www.a20-app-134.online
```

## 9. Verification Checklist

Run these checks from your local machine:

```powershell
Resolve-DnsName a20-app-134.online
Resolve-DnsName www.a20-app-134.online
curl.exe -I http://a20-app-134.online
curl.exe -I https://a20-app-134.online
```

Run these checks on the VM:

```bash
cd ~/A20-App-134/src
docker compose ps
curl http://localhost:8000/health
curl -I http://localhost:5173
sudo nginx -t
sudo systemctl status nginx --no-pager
```

Expected:

- DNS returns `35.200.176.251`.
- Backend health returns `{"ok":true}`.
- Nginx config test returns `syntax is ok` and `test is successful`.
- `https://a20-app-134.online` opens the app without needing `:5173`.

## 10. Troubleshooting

### DNS Does Not Resolve To `35.200.176.251`

Check:

- The A record for `@` points to `35.200.176.251`.
- The `www` record points to `a20-app-134.online` or directly to `35.200.176.251`.
- You edited DNS at the active nameserver provider.
- Old conflicting A or AAAA records were removed.
- Enough time has passed for DNS propagation.

### `http://a20-app-134.online` Does Not Open

Check:

- GCP firewall allows `tcp:80`.
- Nginx is installed and running.
- The Docker containers are running.
- The frontend is reachable on the VM with `curl -I http://localhost:5173`.

### HTTPS Certificate Fails

Check:

- Both `a20-app-134.online` and `www.a20-app-134.online` resolve to `35.200.176.251`.
- GCP firewall allows `tcp:80` and `tcp:443`.
- Nginx passes `sudo nginx -t`.
- Run Certbot again after DNS is correct.

### Login Or Cookies Fail After HTTPS

Check `.env`:

```text
FRONTEND_ORIGIN=https://a20-app-134.online,https://www.a20-app-134.online
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

Then restart:

```bash
docker compose up -d --build
```

## References

- Hostinger Help Center: Manage A records at Hostinger: <https://www.hostinger.com/support/4468886/>
- Hostinger Help Center: Where to find Hostinger nameservers: <https://support.hostinger.com/en/articles/1583247-where-to-find-hostinger-nameservers>
- Google Cloud: Configure static external IP addresses: <https://cloud.google.com/compute/docs/ip-addresses/configure-static-external-ip-address>
- Google Cloud: Compute Engine IP addresses: <https://cloud.google.com/compute/docs/ip-addresses>
