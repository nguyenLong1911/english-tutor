# Hướng dẫn tạo CI/CD với GitHub Actions để auto deploy lên GCP VM

Tài liệu này hướng dẫn thiết lập pipeline CI/CD đơn giản, dễ vận hành cho repo hiện tại:

- Push code lên branch `main`
- GitHub Actions chạy workflow
- Workflow SSH vào Google Compute Engine VM
- VM `git pull` code mới và chạy lại `docker compose up -d --build`

Mô hình này phù hợp với kiến trúc hiện tại của repo vì app đang chạy bằng Docker Compose trong thư mục [`src`](../src), và backend đã tự chạy migration + seed cơ bản khi container khởi động qua [`src/backend/start.sh`](../src/backend/start.sh).

Tài liệu này nên dùng cùng với:

- [deploy-google-compute-engine.md](deploy-google-compute-engine.md)
- [connect-hostinger-domain-to-gcp-vm.md](connect-hostinger-domain-to-gcp-vm.md)

## 1. Kiến trúc deploy đề xuất

Luồng triển khai:

1. Developer push code lên GitHub.
2. GitHub Actions trigger workflow trên branch `main`.
3. Workflow mở SSH session tới GCP VM.
4. VM vào thư mục project, pull code mới nhất.
5. VM chạy `docker compose up -d --build`.
6. Workflow gọi health check để xác nhận backend đã lên lại thành công.

Ưu điểm:

- Dễ thiết lập.
- Không cần Kubernetes, Artifact Registry hay Cloud Build.
- Phù hợp với app đang deploy trực tiếp bằng một VM.

Hạn chế:

- Deploy diễn ra trực tiếp trên production VM.
- Nếu build lỗi hoặc migration lỗi, deploy sẽ fail ngay trên máy production.
- Chưa có rolling deployment hay zero-downtime thực thụ.

## 2. Điều kiện trước khi làm

Bạn cần có sẵn:

1. Một GitHub repository chứa project này.
2. Một GCP VM đã cài Docker và Docker Compose.
3. App đã từng chạy thành công trên VM theo tài liệu [deploy-google-compute-engine.md](deploy-google-compute-engine.md).
4. VM có thể SSH bằng private key.
5. Repo trên VM nằm ở đường dẫn cố định, ví dụ:

```bash
~/A20-App-134
```

6. File môi trường production đã tồn tại trên VM:

```bash
~/A20-App-134/src/.env
```

Không nên để GitHub Actions ghi đè file `.env` mỗi lần deploy nếu app đang chạy production ổn định. An toàn hơn là quản lý `.env` trực tiếp trên VM.

## 3. App hiện tại deploy như thế nào

Các điểm quan trọng riêng của repo này:

- Docker Compose file nằm ở `src/docker-compose.yml`.
- App cần chạy lệnh deploy từ thư mục `src`.
- Backend public ở port `8000`.
- Frontend public ở port `5173`.
- Health endpoint:

```text
http://localhost:8000/health
http://localhost:8000/ready
```

- Khi backend start, script [`src/backend/start.sh`](../src/backend/start.sh) tự chạy:

```bash
alembic upgrade head
python -m app.seeders.seed_processed --only vocabulary,error_bank,pedagogical_prompt,ielts_writing_sample
```

Vì vậy deploy thường không cần gọi migration thủ công thêm một lần nữa.

## 4. Chuẩn bị VM cho deploy bằng SSH

## 4.1. Tạo SSH key riêng cho GitHub Actions

Trên máy local của bạn, tạo một key mới chỉ dùng cho CI/CD:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f github-actions-deploy
```

Bạn sẽ có:

- `github-actions-deploy` là private key
- `github-actions-deploy.pub` là public key

## 4.2. Thêm public key vào VM

SSH vào VM bằng cách bạn đang dùng hiện tại, sau đó thêm public key vào file `authorized_keys`:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
```

Dán nội dung của `github-actions-deploy.pub` vào cuối file, lưu lại, rồi chạy:

```bash
chmod 600 ~/.ssh/authorized_keys
```

## 4.3. Kiểm tra repo trên VM

Trên VM, đảm bảo các lệnh sau chạy được:

```bash
cd ~/A20-App-134
git status
cd src
docker compose ps
```

Nếu repo chưa có trên VM, làm theo phần clone project trong [deploy-google-compute-engine.md](deploy-google-compute-engine.md).

## 4.4. Tạo script deploy trên VM

Tạo file:

```bash
mkdir -p ~/deploy
nano ~/deploy/deploy_a20.sh
chmod +x ~/deploy/deploy_a20.sh
```

Nội dung đề xuất:

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/A20-App-134"
SRC_DIR="$APP_DIR/src"
BRANCH="main"

echo "[deploy] go to repo"
cd "$APP_DIR"

echo "[deploy] fetch latest code"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "[deploy] rebuild containers"
cd "$SRC_DIR"
docker compose up -d --build

echo "[deploy] wait a bit for services"
sleep 10

echo "[deploy] service status"
docker compose ps

echo "[deploy] backend health"
curl --fail http://localhost:8000/health

echo
echo "[deploy] backend ready"
curl --fail http://localhost:8000/ready
```

Lưu ý:

- `git reset --hard` trong script này chỉ nên dùng nếu VM là máy deploy chuyên dụng, không sửa code trực tiếp trên đó.
- Nếu bạn có thói quen chỉnh file ngay trên VM, đổi sang:

```bash
git pull origin main
```

Tuy nhiên cách đó kém ổn định hơn nếu repo trên VM bị lệch trạng thái.

## 5. Tạo GitHub Secrets

Vào GitHub repo:

```text
Settings > Secrets and variables > Actions
```

Tạo các secrets sau:

### `GCP_VM_HOST`

Public IP hoặc domain của VM, ví dụ:

```text
34.101.xx.xx
```

### `GCP_VM_USER`

User dùng để SSH vào VM, ví dụ:

```text
admin
```

hoặc:

```text
your-linux-username
```

### `GCP_VM_SSH_KEY`

Toàn bộ nội dung private key `github-actions-deploy`.

Ví dụ bắt đầu bằng:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

### `GCP_VM_PORT`

Nếu SSH dùng port mặc định thì đặt:

```text
22
```

### `GCP_VM_DEPLOY_SCRIPT`

Đường dẫn script deploy trên VM:

```text
/home/<username>/deploy/deploy_a20.sh
```

Ví dụ:

```text
/home/admin/deploy/deploy_a20.sh
```

## 6. Tạo GitHub Actions workflow

Tạo file:

```text
.github/workflows/deploy-gcp-vm.yml
```

Nội dung mẫu:

```yaml
name: Deploy to GCP VM

on:
  push:
    branches:
      - main
  workflow_dispatch:

concurrency:
  group: deploy-production
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Start ssh-agent and add key
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.GCP_VM_SSH_KEY }}

      - name: Add VM host to known_hosts
        run: |
          mkdir -p ~/.ssh
          ssh-keyscan -p "${{ secrets.GCP_VM_PORT }}" -H "${{ secrets.GCP_VM_HOST }}" >> ~/.ssh/known_hosts

      - name: Run deploy script on VM
        run: |
          ssh -p "${{ secrets.GCP_VM_PORT }}" "${{ secrets.GCP_VM_USER }}@${{ secrets.GCP_VM_HOST }}" \
            "bash '${{ secrets.GCP_VM_DEPLOY_SCRIPT }}'"
```

Workflow này làm đúng ba việc:

1. Nạp private SSH key từ GitHub Secrets.
2. Trust host key của VM.
3. SSH vào VM và chạy script deploy.

## 7. Khuyến nghị thêm bước kiểm tra trước khi deploy

Nếu muốn an toàn hơn, thêm test job trước deploy:

```yaml
name: Deploy to GCP VM

on:
  push:
    branches:
      - main
  workflow_dispatch:

concurrency:
  group: deploy-production
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: src

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install backend dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt

      - name: Run selected tests
        working-directory: src/backend
        run: |
          pytest tests/test_config_urls.py -v
          pytest tests/test_auth_security.py -v

  deploy:
    runs-on: ubuntu-latest
    needs: test

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Start ssh-agent and add key
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.GCP_VM_SSH_KEY }}

      - name: Add VM host to known_hosts
        run: |
          mkdir -p ~/.ssh
          ssh-keyscan -p "${{ secrets.GCP_VM_PORT }}" -H "${{ secrets.GCP_VM_HOST }}" >> ~/.ssh/known_hosts

      - name: Run deploy script on VM
        run: |
          ssh -p "${{ secrets.GCP_VM_PORT }}" "${{ secrets.GCP_VM_USER }}@${{ secrets.GCP_VM_HOST }}" \
            "bash '${{ secrets.GCP_VM_DEPLOY_SCRIPT }}'"
```

Đây chưa phải test coverage đầy đủ, nhưng tốt hơn deploy thẳng mà không có chặn lỗi cơ bản.

## 8. Cách verify sau khi workflow chạy

Sau mỗi lần push lên `main`:

1. Mở tab:

```text
GitHub repo > Actions
```

2. Chọn workflow `Deploy to GCP VM`.
3. Xem step `Run deploy script on VM`.
4. Nếu thành công, kiểm tra app:

```text
http://YOUR_VM_IP:5173
http://YOUR_VM_IP:8000/docs
```

5. Nếu cần, SSH vào VM và kiểm tra:

```bash
cd ~/A20-App-134/src
docker compose ps
docker compose logs -f backend
```

## 9. Rollback thủ công khi deploy lỗi

Thiết kế ở trên chưa có rollback tự động. Khi cần rollback nhanh:

1. SSH vào VM.
2. Vào repo:

```bash
cd ~/A20-App-134
git log --oneline -n 5
```

3. Checkout commit ổn định gần nhất:

```bash
git checkout <good-commit-sha>
cd src
docker compose up -d --build
```

4. Sau đó cần quyết định lại chiến lược branch vì VM đang ở detached HEAD.

An toàn hơn là sửa code trên branch `main`, push commit fix, rồi để GitHub Actions deploy lại.

## 10. Các lỗi thường gặp

### `Permission denied (publickey)`

Nguyên nhân thường gặp:

- Private key trong `GCP_VM_SSH_KEY` sai.
- Public key chưa được thêm đúng vào `~/.ssh/authorized_keys` trên VM.
- Sai `GCP_VM_USER`.

### `Host key verification failed`

Thường do thiếu bước `ssh-keyscan` hoặc VM đã đổi host key.

### `docker compose` fail khi build

Kiểm tra trên VM:

```bash
cd ~/A20-App-134/src
docker compose logs -f
```

Các nguyên nhân phổ biến:

- `.env` production thiếu biến quan trọng.
- Docker disk đầy.
- Repo pull về chưa đồng bộ hoặc có thay đổi local trên VM.

### Health check không pass

Kiểm tra:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
docker compose logs -f backend
```

Repo này dùng `/ready` cho healthcheck nội bộ của backend container, nên endpoint này phản ánh đúng hơn việc app đã sẵn sàng phục vụ hay chưa.

## 11. Khuyến nghị production

Khi hệ thống lớn hơn, nên cân nhắc:

- Build Docker image trên CI thay vì build trực tiếp trên VM.
- Push image lên Artifact Registry hoặc Docker Hub.
- VM chỉ làm việc `docker pull` + `docker compose up -d`.
- Tách job `test`, `build`, `deploy`.
- Thêm thông báo Slack/Discord khi deploy fail.
- Thêm backup cho Postgres trước các thay đổi schema quan trọng.

Với trạng thái hiện tại của repo, cách deploy qua SSH từ GitHub Actions là điểm cân bằng hợp lý giữa tốc độ triển khai và độ phức tạp vận hành.
