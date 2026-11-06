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

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/import_csv.py        # one time: data/cycles_with_durations.csv -> data/cycles.db
```

### Telegram bot
1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. `copy .env.example .env` and set `TELEGRAM_TOKEN`.
3. Start the bot (`python -m app.bot`), send it `/id`, put the number in `ALLOWED_CHAT_ID` and restart. Only that chat can use the bot.

## Running

```bash
./start_up.sh            # web app + bot (Git Bash)
```
or separately:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0
python -m app.bot
```

- Web app: http://127.0.0.1:8000. From your phone on the same Wi-Fi: `http://<PC-IP>:8000`, then "Add to Home Screen".
- API docs: http://127.0.0.1:8000/docs

## Bot commands

| Command | Description |
|---|---|
| `/prossimo` (`/predict`) | Predicted date, window, end date, method |
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
```

## Tests

```powershell
python -m pytest
```

## Privacy

`data/` (CSV and `cycles.db`) and `.env` are in `.gitignore`: health data and the token never end up in git.
