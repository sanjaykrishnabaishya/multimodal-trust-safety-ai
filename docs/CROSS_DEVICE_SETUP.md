# TrustScope cross-device setup

TrustScope is a responsive web application. The same build runs in desktop
browsers, laptop browsers, and mobile browsers. A production HTTPS deployment
can also be installed as a Progressive Web App.

## Local laptop and phone testing

### One-command Windows launcher

From the project root, run:

```powershell
.\start_trustscope.ps1
```

The command starts the API and responsive web app in the background, checks
both health endpoints, and prints the correct laptop and private-network phone
URLs. Stop the services with:

```powershell
.\stop_trustscope.ps1
```

Runtime process state and logs are written under `.trustscope-local`, which is
excluded from Git.

### Manual launch

1. Connect the laptop and phone to the same trusted private network.
2. Start the backend from `backend`:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8010
   ```

3. Start the frontend from `frontend`:

   ```powershell
   npm run dev
   ```

4. Find the laptop's private IPv4 address with `ipconfig`.
5. Open `http://<laptop-private-ip>:5173` on the phone.

The frontend automatically calls port `8010` on the same hostname. The backend
accepts browser requests from localhost and RFC1918 private-network addresses.
Public origins are not accepted by the private-LAN rule.

## Production configuration

Set `VITE_API_BASE_URL` at frontend build time when the API is hosted on a
different HTTPS origin. On the backend, set a comma-separated allowlist:

```text
TRUSTSCOPE_ALLOWED_ORIGINS=https://app.example.com,https://review.example.com
TRUSTSCOPE_ALLOW_PRIVATE_LAN=false
```

Keep all provider keys server-side in local environment variables or a secret
manager. Never embed a key in the frontend bundle, mobile browser storage,
source control, reports, or moderation records.

## Current security boundary

Local private-network access is for controlled development only. Production
still requires authentication, authorization, TLS, encryption at rest, rate
limits, retention controls, and a deployment security review.
