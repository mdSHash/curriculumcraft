# Hosting CurriculumCraft for free

The frontend is hosted on **GitHub Pages** at <https://mdshash.github.io/curriculumcraft/>. It's a static React bundle — there's no server-side code there. To actually generate workbooks you have to run the backend somewhere and tell the deployed frontend how to reach it.

The simplest free setup: **run the backend on your own machine, expose it through a Cloudflare Tunnel, and paste the tunnel URL into the deployed frontend**. No server bill, no deploy step on every push, full performance.

This guide covers two flavors of that setup:

1. **Quick tunnel** — zero accounts, ephemeral URL that changes each run. Best for "I want to try it right now."
2. **Named tunnel** — stable URL, requires a free Cloudflare account and a domain. Best if you'll use it regularly.

> ⚠️ The backend has **no authentication**. Anyone who knows the tunnel URL can use your Gemini API key. With quick tunnels the random URL is effectively the password — don't share it. For a publicly-listed setup, put **Cloudflare Access** in front of the named tunnel, or add an API-key check in the backend, before sharing.

---

## Prerequisites

Once-only setup:

1. Run [setup.bat](setup.bat) (Windows) or [setup.sh](setup.sh) (macOS / Linux) to install backend + frontend dependencies.
2. Edit `backend/.env` and add your `GEMINI_API_KEY`.
3. Install **cloudflared**:
   - **Windows:** `winget install --id Cloudflare.cloudflared` (or download from <https://github.com/cloudflare/cloudflared/releases>)
   - **macOS:** `brew install cloudflared`
   - **Linux:** see [Cloudflare's docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) for your distro.

---

## Option 1 — Quick tunnel (easiest)

Each session:

```bash
# Windows
.\run-tunnel.bat

# macOS / Linux
chmod +x run-tunnel.sh && ./run-tunnel.sh
```

The script will:

1. Start the FastAPI backend on `http://localhost:8000`.
2. Run `cloudflared tunnel --url http://localhost:8000`, which prints a URL like

   ```
   https://stocks-treaty-funding-ours.trycloudflare.com
   ```

3. Copy that URL.
4. Open <https://mdshash.github.io/curriculumcraft/> — you'll see an amber "Backend not connected" banner. Click **Connect backend**, paste the URL, click **Test**, then **Save**.

The URL is stored in your browser's localStorage, so the same browser remembers it across page reloads. **A new URL is generated every time you restart the tunnel** — paste the new one in when that happens.

### Stopping

- macOS / Linux: `Ctrl+C` in the launcher terminal stops both the tunnel and the backend.
- Windows: `Ctrl+C` stops the tunnel; close the second "CurriculumCraft backend" window to stop the backend.

---

## Option 2 — Named tunnel (stable URL)

If you want a URL that doesn't change — e.g. `https://mathcraft.your-domain.com` — you need a free Cloudflare account and a domain on Cloudflare's nameservers.

1. **Add your domain to Cloudflare** — sign up at <https://dash.cloudflare.com/sign-up>, follow the "Add a site" flow, and update your registrar's nameservers as instructed. This is free.

2. **Authenticate cloudflared:**

   ```bash
   cloudflared tunnel login
   ```

3. **Create the tunnel:**

   ```bash
   cloudflared tunnel create mathcraft
   ```

4. **Route a hostname to it:**

   ```bash
   cloudflared tunnel route dns mathcraft mathcraft.your-domain.com
   ```

5. **Run the tunnel pointing at the backend** (start the backend separately as before):

   ```bash
   cloudflared tunnel run --url http://localhost:8000 mathcraft
   ```

6. **Save the URL once** in the GitHub Pages frontend — it's stable, you won't need to update it again.

### Lock it down with Cloudflare Access

The named-tunnel flow lets you put **Cloudflare Access** (also free for up to 50 users) in front of the hostname so only emails you list can hit the API. This is the right answer if anyone other than you will be using the URL — without it, the backend is wide open to whoever finds the hostname.

Set that up in the Cloudflare dashboard under **Zero Trust → Access → Applications**.

---

## Configuring the frontend backend URL

Three ways to tell the frontend where the backend lives, in priority order:

1. **In-app setting (recommended for the deployed Pages site):** click the **Connect backend** button in the top banner, paste the URL, hit Save. Stored in `localStorage`.
2. **Build-time env var** (for self-hosted frontend deploys with a fixed URL): set `VITE_API_BASE_URL=https://api.example.com` before `npm run build`.
3. **Same-origin (default for local dev):** when running `npm run dev`, Vite proxies `/api/*` to `http://localhost:8000`. No config needed.

To clear a saved URL, open the **Connect backend** modal and click **Clear / reset to default**.

---

## Troubleshooting

- **"CORS blocked" in the browser console** — make sure your `backend/.env` has `CORS_ORIGINS=http://localhost:5173,https://mdshash.github.io` (the value already shipped in `.env.example`). If you forked the repo to a different GitHub account, replace `mdshash` with your username.
- **"Backend unreachable" even though `cloudflared` is running** — check the URL ends without a trailing slash and that the backend's `/api/health` returns 200 when you hit `http://localhost:8000/api/health` directly.
- **Uploads time out** — Cloudflare Tunnel has a request body cap (~100 MB on quick tunnels). Make sure `MAX_PDF_SIZE_MB` in `.env` is set sensibly.
- **Tunnel is slow** — the bottleneck is usually the embeddings model + LLM call, not the tunnel. Check the backend logs.
