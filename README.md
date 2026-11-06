# poc_cycle

A personal app that predicts the next period start. Pure Python:

- **FastAPI** backend + **SQLite** storage
- **Mobile web app** (Italian UI, installable on the phone's home screen)
- **Telegram bot** to predict, log data points, view stats, and receive reminders

## How the prediction works

1. Each data point is a **start date**. The **end date** is always start + 6 (7 days of bleeding). The **cycle length** is calculated as the days since the previous start.
2. Intervals longer than **45 days** are flagged as gaps (probably unlogged cycles). They are excluded from statistics and training. Backfilling the missing date clears the flag automatically.
3. Several candidate models (12-cycle median, EWMA, lag-feature linear regression, ARIMA) are scored with a **walk-forward backtest** over the last 24 cycles. The one with the lowest mean absolute error (MAE) is used.
4. **Fallback:** if the model's prediction differs from the median of the last 12 cycles by more than `max(3 days, 1.5×std)`, or falls outside 20–45 days, the median is used instead. The method used is always shown.
5. The **window** is the 25th–75th percentile of the last 12 cycles, always widened to contain the predicted date.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\import_csv.py        # optional: start_up.ps1 does this on the first run
```

The import loads `data\cycles_with_durations.csv` into `data\cycles.db`. It is safe to re-run: dates already present are skipped.

### Telegram bot
1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. `copy .env.example .env` and set `TELEGRAM_TOKEN`.
3. Start the bot, send it `/id`, put the number in `ALLOWED_CHAT_ID` in `.env`, and restart. Only that chat can use the bot, and reminders are sent only once `ALLOWED_CHAT_ID` is set.

## Running

```powershell
.\start_up.ps1
```

The script:
- uses `.venv\Scripts\python.exe` directly (no need to activate the venv)
- imports the CSV on the first run, if `data\cycles.db` doesn't exist
- starts the web app in the background and prints the URLs to open
- runs the bot in the same window if `TELEGRAM_TOKEN` is set in `.env`; otherwise it starts only the web app
- stops everything on Ctrl+C

To run the pieces separately (with the venv activated):
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
python -m app.bot
```

| What | URL |
|---|---|
| Web app on this PC | http://127.0.0.1:8000 |
| Web app from your phone (same Wi-Fi) | `http://<PC-IP>:8000`, printed by `start_up.ps1` (e.g. `http://192.168.1.64:8000`) |
| API docs | http://127.0.0.1:8000/docs |

On the phone, open the URL and choose **Add to Home Screen** to install it like an app.

## Troubleshooting

- **`ERR_ADDRESS_INVALID` on `http://0.0.0.0:8000`**: `0.0.0.0` is only the address the server listens on (all interfaces), not one you can open. Use `127.0.0.1` on the PC or the LAN IP from your phone.
- **The phone can't connect**: allow Python through Windows Firewall when prompted (Private networks), and make sure the Wi-Fi network is set to *Private* in Windows. Alternatively, from an administrator PowerShell:
  ```powershell
  New-NetFirewallRule -DisplayName "poc_cycle 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
  ```
- **"Running scripts is disabled on this system"**: run `powershell -ExecutionPolicy Bypass -File .\start_up.ps1`, or once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **Emoji errors (`UnicodeEncodeError`) when printing bot messages in the console**: set `$env:PYTHONIOENCODING = "utf-8"`. Telegram itself is not affected.
- **The bot answers "Non autorizzato"**: `ALLOWED_CHAT_ID` in `.env` doesn't match your chat. Send `/id`, update `.env`, restart.
- **The first prediction is slow (~5 s)**: the model backtest runs once per data change (ARIMA is the slow one); later requests are cached.
- **Reminders are missed when the PC is off**: the bot checks once at start-up too, and reminders tolerate missed days. For always-on reminders, it needs to be hosted somewhere that is always running.

## Bot commands

| Command | Description |
|---|---|
| `/prossimo` (aliases `/next`, `/prediction`, `/predict`) | Predicted date, window, end date, method |
| `/log` | Buttons [Oggi] [Ieri] [Altra data], or `/log 03/11/2026`, `/log ieri` |
| `/storico` | Last 10 cycles with delete buttons |
| `/stats` | Statistics + chart |
| `/test_promemoria` | Shows the reminders that would fire today |
| `/id` | Your chat id |

**Automatic reminders** (every day at 09:00 Europe/Rome, plus at bot start-up):
2 days before → heads-up · on the predicted day → "È iniziato?" with buttons · after the window → nudge every 2 days · 45 days without logging → "hai dimenticato di registrare?" (weekly).

## API (`/api/v1`)

| Method | Path | |
|---|---|---|
| GET | `/predict` | Current prediction |
| GET / POST | `/cycles` | List / add `{"start_date": "2026-11-03"}` |
| DELETE | `/cycles/{id}` | Delete |
| GET | `/stats`, `/stats/chart.png` | Statistics |
| GET | `/backtest` | MAE of each candidate model and the chosen one |
| GET | `/health` | |

## Structure

```
app/
  config.py, db.py, models.py      settings (.env), SQLite, tables Cycle / ReminderLog
  services/cycles.py               add/delete + recalculation of lengths and gaps
  services/reminders.py            reminder logic + Italian date parsing
  forecasting/                     candidates, backtest, predictor (with fallback)
  stats.py, i18n.py                statistics/chart, Italian formatting
  api/v1/endpoints.py              REST API
  web/                             pages (Jinja2 + HTMX), CSS, PWA manifest
  bot/__main__.py                  Telegram bot
scripts/import_csv.py              CSV import
tests/                             pytest
start_up.ps1                       starts web app + bot (Windows)
.env.example                       template for TELEGRAM_TOKEN / ALLOWED_CHAT_ID
```

## Tests

```powershell
python -m pytest
```

## Privacy

`data/` (CSV and `cycles.db`) and `.env` are in `.gitignore`: health data and the token never end up in git.
