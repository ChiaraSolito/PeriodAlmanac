# Deploy plan: PeriodAlmanac on Oracle Cloud (Always Free) + Tailscale

> Status: **approved 2026-11-12**. Cards created: #8–#13 on the PeriodAlmanac_release project.

## Goal
Run the web app and the Telegram bot 24/7 on a free Oracle Cloud server instead of your PC.
- The web app is reachable over HTTPS **only from your devices** (via Tailscale), so it needs no login.
- Your data lives on the server, with nightly backups and a weekly off-site copy to your PC.
- Updating to a new version is one command.

## Target architecture
```
 Phone / PC (Tailscale app)
        │  https://periodalmanac.<tailnet>.ts.net   (private, HTTPS by Tailscale)
        ▼
 Oracle Cloud VM — Ubuntu 24.04 Arm (VM.Standard.A1.Flex, 1 OCPU / 6 GB), region Milan
   ├─ tailscale serve ──► 127.0.0.1:8000
   └─ docker compose
        ├─ web  : uvicorn app.main:app (no --reload), bound to 127.0.0.1:8000 only
        ├─ bot  : python -m app.bot (polling: needs outbound internet only)
        └─ volume ./data  → cycles.db, backups/
   cron: nightly backup of cycles.db (kept 14 days)
        │
        └─ weekly scp over Tailscale ──► your PC (Windows scheduled task)
```
No ports are opened to the internet. Once Tailscale works, public SSH (port 22) is closed too.

---

## Part 0: Housekeeping (me, ~5 min)
- Open a small PR `feat/cycle-app → main` with the 2 commits that missed PR #7 (bot command menu, README rename).
- Create branch `feat/deploy-oracle` from the updated `main` for the code below.

## Part 1: Code changes in the repo (me)
### 1.1 Containerization
- `Dockerfile`: `python:3.11-slim` (multi-arch, works on Arm), installs `requirements.txt`, runs as a non-root user, `TZ=Europe/Rome`.
- `.dockerignore`: excludes `.venv`, `data/`, `.env`, `notebooks/`, `tests/`, `.git`.
- `docker-compose.yml`:
  - `web`: `uvicorn app.main:app --host 0.0.0.0 --port 8000`, port mapped as `127.0.0.1:8000:8000` (not public), healthcheck on `/api/v1/health`
  - `bot`: `python -m app.bot`
  - both: `env_file: .env`, volume `./data:/app/data`, `restart: unless-stopped`, log rotation
- Optional split: dev/test dependencies (`pytest`, `httpx`) move to `requirements-dev.txt` so the image is smaller.

### 1.2 SQLite hardening (two processes write to the same file)
- Enable `journal_mode=WAL` and `busy_timeout=5000` on every connection (SQLAlchemy `connect` event in `app/db.py`).
- Test: concurrent writes from two sessions don't raise "database is locked".

### 1.3 Backups
- `scripts/backup_db.py`: consistent copy with SQLite's online backup API → `data/backups/cycles-YYYYMMDD.db`, deletes copies older than 14 days.
- `scripts/restore_db.md` section in DEPLOY.md: stop containers → copy backup over `cycles.db` → start.
- `scripts/pull_backup.ps1` (on your PC): `scp` the latest backup over Tailscale into `Documents\PeriodAlmanac-backups\`; registered as a weekly Windows scheduled task.

### 1.4 Documentation
- `DEPLOY.md`: step-by-step guide for Parts 2–4 below, plus update, restore and troubleshooting.
- README: "Deployment" section linking to DEPLOY.md; `start_up.ps1` stays for local development.

## Part 2: Oracle Cloud setup (you, with DEPLOY.md, ~1 h)
1. Create the account at oracle.com/cloud/free (needs a credit card for verification). **Home region: Italy Northwest (Milan)**, which is permanent.
2. **Upgrade to Pay As You Go** (still €0 within Always Free limits; prevents idle-instance reclamation) and create a **budget alert at €1**.
3. Create the VM: Ubuntu 24.04 aarch64, shape `VM.Standard.A1.Flex`, **1 OCPU / 6 GB**, add your SSH public key. If you get "Out of host capacity", retry later or switch availability domain.
4. SSH in once with the public IP and run the bootstrap commands from DEPLOY.md: system updates, `unattended-upgrades`, Docker Engine + compose plugin.

## Part 3: Tailscale (you, ~20 min)
1. Create a Tailscale account (free personal plan); install the app on **phone** and **PC**.
2. On the server: install Tailscale, `sudo tailscale up --hostname periodalmanac`. SSH stays plain OpenSSH with your key, reached over the Tailscale network (Tailscale SSH's periodic browser re-check would break the unattended weekly backup).
3. Enable **MagicDNS** and **HTTPS certificates** in the Tailscale admin console.
4. Verify `ssh periodalmanac` works over Tailscale, then **remove the port 22 ingress rule** in the Oracle security list.

## Part 4: Go-live (you + me)
1. On the server: `git clone` the repo.
2. From your PC (over Tailscale): copy `.env` and `data/cycles.db` to the server.
3. **Stop the bot on your PC** (Telegram allows only one polling instance).
4. On the server: `docker compose up -d --build`, then `sudo tailscale serve --bg 8000`.
5. Check:
   - `https://periodalmanac.<tailnet>.ts.net` opens on the phone; "Add to Home Screen"
   - `/prossimo` and `/test_promemoria` answer in Telegram
   - `docker compose ps` shows both services healthy
   - reboot the VM and confirm everything comes back by itself
6. Install the backup cron entry and the weekly pull task on your PC; run each once by hand.

## Updating later
```bash
ssh periodalmanac
cd PeriodAlmanac && git pull && docker compose up -d --build
```

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| Oracle reclaims an idle Always Free VM | Pay As You Go upgrade (still free within limits) |
| Unexpected charges after the upgrade | Budget alert at €1; stay on Always Free shapes only |
| Oracle closes the account | Weekly off-site backup to your PC; the whole setup is reproducible from DEPLOY.md |
| "Out of host capacity" for Arm VMs | Retry or switch availability domain; fallback: AMD micro (1 GB) with swap |
| Two bot instances running | Go-live checklist step: stop the local bot first |
| SQLite "database is locked" | WAL + busy_timeout (1.2) |

## Decisions
1. **Off-site backup:** weekly pull to your PC over Tailscale.
2. **Card language:** Italian.
3. **Server size:** 1 OCPU / 6 GB.

---

# Proposed project cards (PeriodAlmanac_release)

Created as issues #8–#13: **Status Backlog**, assignee ChiaraSolito, created as issues in `ChiaraSolito/PeriodAlmanac` and added to project 1.

| # | Title | Area | Type | Priority | Size | Who |
|---|---|---|---|---|---|---|
| A (#8) | [Infra] Containerizzazione con Docker Compose | Infra | Feature | High | M | me |
| B (#9) | [Backend] SQLite in WAL e backup automatici | Backend | Feature | High | S | me |
| C (#10) | [Docs] Guida di deploy (DEPLOY.md) | Infra | Docs | High | S | me |
| D (#11) | [Infra] Server Oracle Cloud Always Free | Infra | Chore | High | M | you |
| E (#12) | [Infra] Accesso privato con Tailscale + HTTPS | Infra | Chore | High | S | you |
| F (#13) | [Infra] Go-live: migrazione dati e spegnimento bot locale | Infra | Chore | Medium | S | you + me |

Order: A, B, C (one PR `feat/deploy-oracle`, closes #8–#10) → D → E → F.

### A (#8). [Infra] Containerizzazione con Docker Compose
**Descrizione**: Impacchettare web app e bot in container per eseguirli sul server.
**Criteri di accettazione**
- [ ] `Dockerfile` multi-arch (funziona su Arm), utente non-root, `TZ=Europe/Rome`
- [ ] `.dockerignore` (esclude `.venv`, `data/`, `.env`, `notebooks/`, `tests/`)
- [ ] `docker-compose.yml` con servizi `web` e `bot`, volume `./data`, `env_file: .env`, `restart: unless-stopped`
- [ ] La web app è esposta solo su `127.0.0.1:8000` (nessuna porta pubblica)
- [ ] Healthcheck su `/api/v1/health`
- [ ] `docker compose up -d --build` funziona in locale

### B (#9). [Backend] SQLite in WAL e backup automatici
**Descrizione**: Rendere sicure le scritture concorrenti di bot e web app e garantire backup recuperabili.
**Criteri di accettazione**
- [ ] `journal_mode=WAL` e `busy_timeout` su ogni connessione
- [ ] Test con scritture concorrenti senza "database is locked"
- [ ] `scripts/backup_db.py`: copia consistente in `data/backups/`, conserva 14 giorni
- [ ] `scripts/pull_backup.ps1`: copia settimanale dell'ultimo backup sul PC via Tailscale
- [ ] Procedura di ripristino documentata e provata una volta

### C (#10). [Docs] Guida di deploy (DEPLOY.md)
**Descrizione**: Guida passo-passo per creare il server, installare l'app, aggiornarla e ripristinarla.
**Criteri di accettazione**
- [ ] Setup Oracle (account, Pay As You Go, budget alert, VM Arm)
- [ ] Bootstrap server (aggiornamenti, Docker, unattended-upgrades)
- [ ] Tailscale (installazione, MagicDNS, HTTPS, `tailscale serve`, chiusura porta 22)
- [ ] Go-live, aggiornamento, backup/ripristino, troubleshooting
- [ ] README con sezione "Deployment" che rimanda a DEPLOY.md

### D (#11). [Infra] Server Oracle Cloud Always Free
**Descrizione**: Creare il server su cui gira l'app.
**Criteri di accettazione**
- [ ] Account Oracle con home region Milano
- [ ] Upgrade a Pay As You Go + budget alert a €1
- [ ] VM Ubuntu 24.04 Arm `VM.Standard.A1.Flex` 1 OCPU / 6 GB con chiave SSH
- [ ] Bootstrap eseguito (Docker, aggiornamenti automatici)

### E (#12). [Infra] Accesso privato con Tailscale + HTTPS
**Descrizione**: Rendere la web app raggiungibile solo dai miei dispositivi, in HTTPS.
**Criteri di accettazione**
- [ ] Tailscale su server, telefono e PC; MagicDNS e certificati HTTPS attivi
- [ ] SSH via Tailscale funzionante, poi regola della porta 22 rimossa su Oracle
- [ ] `tailscale serve` espone la web app su `https://periodalmanac.<tailnet>.ts.net`

### F (#13). [Infra] Go-live: migrazione dati e spegnimento bot locale
**Descrizione**: Spostare dati e servizi dal PC al server.
**Criteri di accettazione**
- [ ] `.env` e `cycles.db` copiati sul server
- [ ] Bot locale spento prima dell'avvio sul server
- [ ] `docker compose up -d` ok; web app aperta dal telefono e installata in Home
- [ ] `/prossimo` e `/test_promemoria` funzionano su Telegram
- [ ] Dopo un riavvio della VM tutto riparte da solo
- [ ] Cron del backup notturno e task settimanale sul PC attivi e provati
