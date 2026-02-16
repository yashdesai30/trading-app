## Sensex / Nifty Ratio Monitor

This is a **simple app** that shows live Sensex and Nifty prices from **Groww's Trade API**. You can run it **on your computer** (desktop window) or **in a web browser**—including on your **phone**—so you can watch the ratios from anywhere.

On the screen you will see:

- **Nifty & Sensex futures prices** and their **ratio**
- **Nifty & Sensex cash prices** and their **ratio**
- Counts of how many times the ratio crosses key thresholds (3.25 / 3.26)

Everything below is written for someone who has **never installed Python before**.

---

### 1. Install Python

You need Python version **3.10 or higher**.

- **On Windows**
  1. Go to the official Python website: `https://www.python.org/downloads/`
  2. Click **Download Python 3.x.x** for Windows.
  3. Run the installer.
  4. On the first screen, make sure you tick **“Add Python to PATH”**.
  5. Click **Install Now** and finish the installation.

- **On macOS**
  1. Go to `https://www.python.org/downloads/`
  2. Download the latest **macOS installer**.
  3. Open the `.pkg` file and follow the steps to install.

To check that Python is installed correctly:

- Open **Command Prompt** (Windows) or **Terminal** (macOS).
- Type:

  ```bash
  python --version
  ```

  or, if that does not work:

  ```bash
  python3 --version
  ```

You should see something like `Python 3.10.0` or higher.

---

### 2. Download this project

You need the project files on your computer.

1. Put the project folder (the one that contains `app.py`, `config.py`, etc.) somewhere easy, for example: `C:\sensex-nifty-app` on Windows or your home folder on macOS.
2. Open **Command Prompt / Terminal**.
3. Go inside the project folder. For example:

   - Windows:

     ```bash
     cd C:\sensex-nifty-app
     ```

   - macOS:

     ```bash
     cd ~/sensex-nifty-app
     ```

All the next commands should be run **inside this folder**.

---

### 3. (Optional but recommended) Create a virtual environment

A “virtual environment” keeps the Python packages for this project separate from other things on your computer.

- Windows:

  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  ```

- macOS:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

After activation, your prompt will usually start with `(.venv)` which is expected.

If you don’t understand this, you can skip it and just install packages globally, but the above is safer.

---

### 4. Install required Python packages

Still in the project folder, run:

```bash
pip install -r requirements.txt
```

If `pip` is not found, try:

```bash
python -m pip install -r requirements.txt
```

or on macOS:

```bash
python3 -m pip install -r requirements.txt
```

---

### 5. Groww Trade API details you need

You need an **active Groww Trading API subscription** and API credentials.

- Get an API key (and optionally secret or TOTP) from [Groww Cloud API Keys](https://groww.in/trade-api/api-keys).
- You can use either:
  - **Access token** (expires daily at 6:00 AM) from your [Trading APIs profile](https://groww.in/user/profile/trading-apis), or
  - **API Key + Secret** (approve the key daily on the API Keys page), or
  - **API Key + TOTP** (no daily expiry; generate token at startup).

**Recommendation:** Use **API Key + TOTP** for deployed or long-term use—set it once and the app gets a valid token at startup with no daily refresh. Use **Access token** only for quick local testing.

---

### 6. Configuration (`.env` file)

The app reads configuration from environment variables. Create a file called `.env` in the project folder.

**Option A – Access token (simplest, expires daily):**

```bash
GROWW_ACCESS_TOKEN=your_access_token_here
```

**Option B – API Key + Secret (approve key daily at Groww):**

```bash
GROWW_API_KEY=your_api_key
GROWW_API_SECRET=your_api_secret
```

**Option C – API Key + TOTP (no daily expiry):**

```bash
GROWW_API_KEY=your_api_key
GROWW_TOTP_SECRET=your_totp_secret
```

**How to get the TOTP secret:** You don’t generate it yourself—Groww gives it to you when you create a TOTP key.

1. Go to [Groww Cloud API Keys](https://groww.in/trade-api/api-keys) and log in.
2. Click the **“Generate API key”** dropdown and choose **“Generate TOTP token”**.
3. Enter a name for the key and continue.
4. Groww will show:
   - **TOTP token** → use this as `GROWW_API_KEY`
   - **Secret** (a string, or a QR code you can scan) → use the **raw secret string** as `GROWW_TOTP_SECRET`

Copy the secret into your `.env` as `GROWW_TOTP_SECRET`. Do not use the 6-digit code from an authenticator app there—the app uses the secret to generate that code at runtime.

If you get **400 Bad Request** with TOTP: use the **same** API key that Groww showed when you created the TOTP token (the dropdown “Generate TOTP token”, not “Generate API key”). The key and secret are a pair. If it still fails, use **API Key + Secret** instead and approve the key daily at [Groww API Keys](https://groww.in/trade-api/api-keys).

Save the `.env` file. The app will read it when it runs.

---

### 7. Generating the access token (if using API Key + Secret)

If you use **GROWW_API_KEY** and **GROWW_API_SECRET**, you must **approve the key for the day** at [Groww Cloud API Keys](https://groww.in/trade-api/api-keys), then generate a token:

1. In `.env` set `GROWW_API_KEY` and `GROWW_API_SECRET`.
2. Approve the key for today on the Groww API Keys page.
3. Run:

   ```bash
   python generate_token.py
   ```

4. Copy the printed `GROWW_ACCESS_TOKEN=...` line into your `.env`.

Alternatively, use **TOTP** (Option C above) so the app generates the token at startup and you don’t need to refresh daily.

---

### 8. Optional futures configuration

By default, the app resolves the nearest Nifty and Sensex futures from Groww’s instruments CSV.

To override, set in `.env`:

- `NIFTY_FUT_EXCHANGE_TOKEN` – exchange token for Nifty futures (from [instruments CSV](https://growwapi-assets.groww.in/instruments/instrument.csv))
- `SENSEX_FUT_EXCHANGE_TOKEN` – exchange token for Sensex futures

---

### 9. Running the app (desktop window)

From the project directory:

```bash
python app.py
```

If that does not work, try:

```bash
python3 app.py
```

A window titled **"Sensex / Nifty – Cash & Futures"** will open and start updating as live ticks arrive (as long as the market is open and your access token is valid).

---

### 10. Running on your phone (or in any browser)

You can view the same live data on your **mobile phone** or any device with a browser. Your computer runs a small web server and your phone just opens a webpage.

1. **On your computer** (same project folder, same `.env` and access token as above), run the **web server**:

   ```bash
   python server.py
   ```

   If that does not work, try `python3 server.py`.

2. You will see a message like:
   - **Open in browser: http://0.0.0.0:8000**
   - **On this machine: http://127.0.0.1:8000**

3. **On this computer:** open a browser and go to **http://127.0.0.1:8000**. You will see the same prices and ratios in a mobile-friendly page.

4. **On your phone:**  
   - Make sure your phone is on the **same Wi‑Fi** as the computer.  
   - Find your computer’s **IP address**:
     - **Windows:** Open Command Prompt and type `ipconfig`. Look for “IPv4 Address” (e.g. `192.168.1.5`).
     - **macOS:** Open Terminal and type `ipconfig getifaddr en0` (or `en1` if you use Ethernet). You’ll see something like `192.168.1.5`.
   - On your phone’s browser, go to **http://192.168.1.5:8000** (use your computer’s actual IP instead of `192.168.1.5`).

The page will update in real time. You can leave the server running on your computer and use your phone to check the ratios whenever you want.

---

### 11. Live data in Excel or Google Sheets

The app exposes the current state so you can pull it into a spreadsheet.

**Endpoints (use your app’s base URL, e.g. `https://your-app.onrender.com`):**

- **JSON:** `GET /api/state` — returns all metrics as JSON.
- **CSV:** `GET /api/state.csv` — returns the same data as CSV.

**Google Sheets**

- **Option A – Auto-refresh every minute:**  
  1. Extensions → Apps Script.  
  2. Paste a script that fetches your URL and writes to the sheet, e.g.:
     ```js
     function updateData() {
       var url = "https://YOUR-APP-URL/api/state";
       var res = UrlFetchApp.fetch(url);
       var data = JSON.parse(res.getContentText());
       var sheet = SpreadsheetApp.getActiveSheet();
       sheet.getRange("A1").setValue("Nifty Fut"); sheet.getRange("B1").setValue(data.nifty_fut);
       sheet.getRange("A2").setValue("Sensex Fut"); sheet.getRange("B2").setValue(data.sensex_fut);
       sheet.getRange("A3").setValue("Fut Ratio"); sheet.getRange("B3").setValue(data.fut_ratio);
       sheet.getRange("A4").setValue("Nifty Cash"); sheet.getRange("B4").setValue(data.nifty_cash);
       sheet.getRange("A5").setValue("Sensex Cash"); sheet.getRange("B5").setValue(data.sensex_cash);
       sheet.getRange("A6").setValue("Cash Ratio"); sheet.getRange("B6").setValue(data.cash_ratio);
     }
     ```
  3. Run `updateData` once. Then set a trigger: Edit → Current project’s triggers → Add trigger → `updateData`, Time-driven, every 1 minute (or 5 minutes).
- **Option B – CSV (manual refresh):** In a cell use `=IMPORTDATA("https://YOUR-APP-URL/api/state.csv")`. Sheets will refresh the import periodically (often hourly); for more frequent updates use Option A.

**Excel**

- **Get Data from Web:** Data → Get Data → From Web → enter `https://YOUR-APP-URL/api/state`. Excel will parse the JSON. Load to a table, then Data → Refresh All. Set the query to refresh every 1–5 minutes: Right-click the query → Properties → Refresh every N minutes.

Data is as live as your refresh interval (e.g. every 1–5 minutes). The app updates in memory in real time; the sheet sees the latest values when it fetches the URL.

---

#### Live push to Google Sheets (no delay)

The app can **push** the latest state to a Google Sheet as soon as new data arrives (throttled to about every 2 seconds to respect API limits). The sheet updates with almost no delay.

**Setup:**

1. **Google Cloud:** Go to [Google Cloud Console](https://console.cloud.google.com) → create or select a project → **APIs & Services** → **Enable APIs** → enable **Google Sheets API**.
2. **Service account:** **APIs & Services** → **Credentials** → **Create credentials** → **Service account**. Create it, then open it → **Keys** → **Add key** → **Create new key** → JSON. Download the JSON file.
3. **Share the Sheet:** Open your Google Sheet. Copy its ID from the URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`. Click **Share**, add the **service account email** (from the JSON, e.g. `xxx@yyy.iam.gserviceaccount.com`) as **Editor**.
4. **Configure the app:**
   - **GOOGLE_SHEET_ID** = the sheet ID from the URL (required).
   - **GOOGLE_SHEET_RANGE** = range to write to (optional, default `Sheet1!A1:B11`). The app writes a header row and 10 rows of metrics.
   - Credentials (one of):
     - **GOOGLE_APPLICATION_CREDENTIALS** = path to the service account JSON file (e.g. `./secrets/sheets-key.json`), or
     - **GOOGLE_SHEETS_CREDENTIALS_JSON** = the **entire** JSON content of the key as a string (useful on Render: paste the JSON into an env var; escape newlines or use a single line).

After that, whenever the Groww feed updates the app’s state, the app pushes the new values to the sheet (at most every 2 seconds). The sheet updates live with minimal delay.

---

### 12. Hosting the app online (so you don’t run the server yourself)

You can deploy the **web app** to a hosting service. Then you (and your phone) just open a URL—no need to keep your computer on or run `server.py` yourself.

**Important:** If you use **GROWW_ACCESS_TOKEN**, it expires daily at 6:00 AM. Refresh it via `/token` (after approving the key at Groww) or run `generate_token.py` and update the env var. Using **GROWW_TOTP_SECRET** avoids daily refresh.

#### Deploy to Render (recommended)

This project includes a **Render Blueprint** (`render.yaml`):

1. Push this project to **GitHub**.
2. Go to [render.com](https://render.com) and sign up or log in.
3. Click **New** → **Blueprint**, connect GitHub, and select this repo.
4. Render will create a web service **sensex-nifty-ratio**. In **Environment** set:
   - **GROWW_ACCESS_TOKEN** (or use **GROWW_API_KEY** + **GROWW_API_SECRET** or **GROWW_TOTP_SECRET**).
5. Deploy. Open the URL Render gives you.

**Refreshing the token:** Open `/token` in the app. If **GROWW_API_KEY** and **GROWW_API_SECRET** are set in Render’s Environment, approve the key for today at [Groww API Keys](https://groww.in/trade-api/api-keys), then click **Regenerate token** on `/token`. Optional: set **REFRESH_SECRET** to require a password for that button.

Manual setup: **Build command** `pip install -r requirements.txt`, **Start command** `python run_gunicorn.py` (patches eventlet before Gunicorn to avoid the RLock warning). Same env vars as above.

**If the dashboard shows "Connected, waiting for data..." but no numbers:**  
1. In Render → your service → **Environment**, ensure **GROWW_ACCESS_TOKEN** (or **GROWW_API_KEY** + **GROWW_TOTP_SECRET** / **GROWW_API_SECRET**) is set.  
2. If using **GROWW_ACCESS_TOKEN**, it expires daily; refresh via `/token` or update the env var.  
3. Open **Logs** in Render and look for `Groww feed: starting...` and any `Groww feed error:` line.  
4. On the free tier, the service can take 30–60 seconds to wake up; wait and refresh once.

#### Alternative: Railway

1. Create an account at [railway.app](https://railway.app), **New project** → **Deploy from GitHub repo**.
2. In **Variables** add `GROWW_ACCESS_TOKEN` (or `GROWW_API_KEY` + `GROWW_API_SECRET` / `GROWW_TOTP_SECRET`).
3. Use the generated URL. Refresh token via `/token` or by updating `GROWW_ACCESS_TOKEN` when it expires.

**Using the API in Sheets/Excel:** Use the same URL as above: `https://your-app.onrender.com/api/state` (JSON) or `.../api/state.csv` (CSV). See section 11.

---

### Notes

- If you use **GROWW_ACCESS_TOKEN**, it expires daily at 6:00 AM; regenerate via `/token` or `generate_token.py` and update your `.env` or host’s environment.
- Using **GROWW_TOTP_SECRET** (with **GROWW_API_KEY**) avoids daily token refresh.
- `.gitignore` is configured so `.env` and the virtual environment are not committed.

---

**Environment variables summary**

- **GROWW_ACCESS_TOKEN** – access token (expires daily), or
- **GROWW_API_KEY** + **GROWW_API_SECRET** – approve key daily at Groww; app or `generate_token.py` can generate token, or
- **GROWW_API_KEY** + **GROWW_TOTP_SECRET** – token generated at startup, no daily expiry.

**Optional:** `NIFTY_FUT_EXCHANGE_TOKEN`, `SENSEX_FUT_EXCHANGE_TOKEN` to override auto-resolved futures. `REFRESH_SECRET` to password-protect the regenerate-token button on `/token`.

**Live push to Google Sheets:** `GOOGLE_SHEET_ID` (required), `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON) or `GOOGLE_SHEETS_CREDENTIALS_JSON` (JSON string), and optionally `GOOGLE_SHEET_RANGE` (default `Sheet1!A1:B11`). See section 11.

