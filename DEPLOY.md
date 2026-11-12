# Deploying PeriodAlmanac on Oracle Cloud + Tailscale

The web app and the Telegram bot run 24/7 on a free Oracle Cloud server.
The web app is reachable over HTTPS **only from your own devices**, through Tailscale; nothing is exposed to the internet.

```
 Phone / PC (Tailscale app)
        │  https://periodalmanac.<tailnet>.ts.net
        ▼
 Oracle VM (Ubuntu 24.04 Arm, 1 OCPU / 6 GB, Milan)
   ├─ tailscale serve ──► 127.0.0.1:8000
   └─ docker compose: web (FastAPI) + bot (Telegram), shared ./data/cycles.db
   cron 03:30: backup → data/backups (14 days)   ──weekly──►  your PC
```

Time needed: about 1.5 hours the first time.
Commands marked **PC** run in PowerShell on your PC; commands marked **server** run over SSH on the VM.

---

## 1. SSH key (PC, once)

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\periodalmanac
```
Leave the passphrase **empty**: the weekly backup task runs unattended and can't type one.
You'll paste the content of `$HOME\.ssh\periodalmanac.pub` into Oracle in step 2.3.

Add this to `$HOME\.ssh\config` (create the file if it doesn't exist), so `ssh ubuntu@periodalmanac` uses the key:
```
Host periodalmanac
    User ubuntu
    IdentityFile ~/.ssh/periodalmanac
```

## 2. Oracle Cloud (browser)

### 2.1 Account
1. Sign up at https://www.oracle.com/cloud/free/ (a credit card is needed for identity verification).
2. **Home region: Italy Northwest (Milan)**. It can't be changed later.

### 2.2 Avoid surprises
1. **Upgrade to Pay As You Go**: *Billing & Cost Management → Upgrade and Manage Payment*.
   You still pay nothing while you stay within the Always Free limits, and Oracle stops reclaiming idle Always Free servers.
2. **Budget alert**: *Billing & Cost Management → Budgets → Create Budget*, amount **1**, alert at 100% of actual spend, to your email.

### 2.3 Create the server
*Compute → Instances → Create instance*:
- **Name**: `periodalmanac`
- **Image**: Canonical Ubuntu 24.04 (the aarch64 build is chosen automatically for Ampere)
- **Shape**: *Change shape → Ampere → `VM.Standard.A1.Flex`*, **1 OCPU, 6 GB** (shown as "Always Free-eligible")
- **Networking**: create a new VCN with a public subnet, **assign a public IPv4 address**
- **SSH keys**: *Paste public keys*, then paste the content of `periodalmanac.pub`
- **Boot volume**: default (about 50 GB, within the free 200 GB)

If you get **"Out of host capacity"**: retry later, or pick another availability domain. Capacity frees up during the day.

### 2.4 First login and bootstrap
**PC** (use the public IP shown on the instance page):
```powershell
ssh -i $HOME\.ssh\periodalmanac ubuntu@<PUBLIC_IP>
```
**server**:
```bash
git clone https://github.com/ChiaraSolito/PeriodAlmanac.git
cd PeriodAlmanac
sudo bash scripts/server/bootstrap.sh
```
This installs system updates, automatic security updates, Docker and Tailscale.

## 3. Tailscale

1. Create a free account at https://tailscale.com and install the app on your **phone** and **PC**. Log in on both.
2. **server**:
   ```bash
   sudo tailscale up --hostname periodalmanac
   ```
   Open the printed link and approve the server.
3. In the Tailscale admin console (https://login.tailscale.com/admin/dns): check that **MagicDNS** is on, and click **Enable HTTPS**.
4. **PC**: check that SSH works over Tailscale:
   ```powershell
   ssh periodalmanac
   ```
5. Only after step 4 works, close public SSH in Oracle:
   *Networking → Virtual cloud networks → (your VCN) → Security Lists → Default Security List → Ingress Rules*: delete the rule for **0.0.0.0/0, TCP port 22**.
   From now on the server is reachable only through Tailscale.

## 4. Go-live

### 4.1 Copy the data
**PC**, in the project folder. Stop the bot on your PC first: Telegram allows only one running bot.
```powershell
# a consistent single-file copy of your database
.\.venv\Scripts\python.exe scripts\backup_db.py --dir data\export
$db = (Get-ChildItem data\export\cycles-*.db | Sort-Object Name | Select-Object -Last 1).FullName

ssh periodalmanac "mkdir -p PeriodAlmanac/data"
scp $db periodalmanac:PeriodAlmanac/data/cycles.db
scp .env periodalmanac:PeriodAlmanac/.env
ssh periodalmanac "chmod 600 PeriodAlmanac/.env"
```

### 4.2 Start
**server** (log out and back in once after the bootstrap, so `docker` works without sudo):
```bash
cd ~/PeriodAlmanac
docker compose up -d --build        # first build takes a few minutes
docker compose ps                   # web should become "healthy"
sudo tailscale serve --bg 8000      # prints https://periodalmanac.<tailnet>.ts.net
```

### 4.3 Check
- [ ] On your phone (Tailscale connected) open `https://periodalmanac.<tailnet>.ts.net`, then *Add to Home Screen*
- [ ] Telegram: `/prossimo` answers, `/test_promemoria` answers
- [ ] **server**: `sudo reboot`, wait a minute, and check that the web app and the bot work again by themselves

### 4.4 Backups
**server**: nightly backup at 03:30, kept 14 days:
```bash
(crontab -l 2>/dev/null | grep -v backup_db.py; echo '30 3 * * * cd $HOME/PeriodAlmanac && mkdir -p data/backups && docker compose exec -T web python scripts/backup_db.py >> data/backups/backup.log 2>&1') | crontab -
cd ~/PeriodAlmanac && docker compose exec -T web python scripts/backup_db.py   # run once now
```
**PC**: weekly copy to `Documents\PeriodAlmanac-backups` (Sundays 20:00, or at the next start-up if the PC was off):
```powershell
.\scripts\pull_backup.ps1            # run once now, to check it works
.\scripts\pull_backup.ps1 -Install   # register the weekly task
```

---

## Everyday operations

| Task | Command (server, in `~/PeriodAlmanac`) |
|---|---|
| Deploy a new version | `git pull && docker compose up -d --build` |
| Logs | `docker compose logs -f bot` / `docker compose logs -f web` |
| Status | `docker compose ps` |
| Restart | `docker compose restart` |
| Manual backup | `docker compose exec -T web python scripts/backup_db.py` |

### Restore a backup
**server**:
```bash
cd ~/PeriodAlmanac
docker compose stop
cp data/backups/cycles-YYYYMMDD.db data/cycles.db
rm -f data/cycles.db-wal data/cycles.db-shm
docker compose start
```
From the copy on your PC: `scp <file> periodalmanac:PeriodAlmanac/data/cycles.db`, after `docker compose stop` and before `docker compose start`, with the same `rm` step.

### Rebuild from zero (e.g. if Oracle closes the account)
Repeat sections 2–4 using the newest file in `Documents\PeriodAlmanac-backups` as the database in step 4.1.

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot logs `Conflict: terminated by other getUpdates request` | Another copy of the bot is running (probably on your PC). Stop it. |
| `permission denied` on `data/` | `sudo chown -R 1000:1000 ~/PeriodAlmanac/data` (the container runs as uid 1000) |
| The phone can't open the site | Is the Tailscale app connected on the phone? `tailscale serve status` on the server |
| Certificate warning on first visit | Wait a minute: Tailscale issues the certificate on first use |
| `ssh periodalmanac` fails | Is Tailscale running on the PC? `tailscale status` should list `periodalmanac` |
| Weekly backup failed | Look at `Documents\PeriodAlmanac-backups\pull.log` |
| "Out of host capacity" when creating the VM | Retry later or use another availability domain |
| Unexpected Oracle bill | Check the budget alert; only Always Free shapes (A1 Flex up to 4 OCPU / 24 GB in total) are free |
