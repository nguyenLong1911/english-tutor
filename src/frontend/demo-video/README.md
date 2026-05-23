# Demo video recorder

Module nay dung Playwright de mo frontend, thuc hien mot luong demo san pham khoang 1 phut va luu video WebM.

## Chay nhanh

```bash
cd src/frontend
npm run demo:video
```

Video duoc copy ra:

```text
output/demo-video/english-tutor-ai-demo.webm
```

## Video chat memory ca nhan hoa

```bash
cd src/frontend
npm run demo:chat-memory
```

Video duoc copy ra:

```text
output/demo-video/english-tutor-ai-chat-memory-demo.webm
```

Lan dau chay Playwright tren may moi co the can cai browser:

```bash
npx playwright install chromium
```

## Ghi chu

- Script tu khoi dong Vite neu `DEMO_BASE_URL` khong duoc set.
- API duoc mock trong `demo-video.spec.js`, nen khong can backend, database hay LLM provider dang chay.
- Video co hieu ung trong luc quay: zoom vung chat, ve khung do quanh tu/cum tu can nhan manh, va hien callout ngan.
- Neu muon quay app dang chay san, dat `DEMO_BASE_URL`, vi du:

```bash
DEMO_BASE_URL=http://127.0.0.1:5173 npm run demo:video
```
