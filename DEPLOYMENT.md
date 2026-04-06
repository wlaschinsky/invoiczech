# VPS Deployment Guide

Průvodce nasazením Python (FastAPI) appek na vlastní VPS. Obecný postup + specifika pro InvoiCzech.

## 1. Infrastruktura

### Server
- **Poskytovatel:** Hetzner Cloud (doporučeno)
- **Typ:** CAX11 nebo CX23 (2 vCPU, 4 GB RAM, 40 GB SSD)
- **Cena:** ~3.50–4.00 EUR/měsíc
- **OS:** Ubuntu 24.04
- **Přihlášení:** `ssh uzivatel@IP_SERVERU`

### Doména
- **Poskytovatel:** Wedos, Forpsi nebo jiný český registrátor
- **Propojení:** A záznamy v DNS ukazují na IP serveru
- **Struktura:** jedna hlavní doména + subdomény pro každou appku

---

## 2. DNS záznamy

| Název | Typ | Hodnota | TTL |
|-------|-----|---------|-----|
| appka1 | A | IP_SERVERU | 3600 |
| appka2 | A | IP_SERVERU | 3600 |

Každá nová appka = nový A záznam v DNS + nová nginx konfigurace na serveru.

---

## 3. Nastavení serveru (jednorázové)

### Základní balíčky
```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx sqlite3
```

### SSH klíč (na lokálním Macu/PC)
```bash
ssh-keygen -t ed25519 -C "vas@email.com"
cat ~/.ssh/id_ed25519.pub
# zkopíruj výstup → vlož do Hetzneru při vytváření serveru
```

### Uživatel (bezpečnější než běžet jako root)
```bash
adduser --disabled-password --gecos "" uzivatel
usermod -aG sudo uzivatel
mkdir -p /home/uzivatel/.ssh
cp ~/.ssh/authorized_keys /home/uzivatel/.ssh/
chown -R uzivatel:uzivatel /home/uzivatel/.ssh
```

---

## 4. Nasazení nové appky

### Krok 1 — Klonování
```bash
git clone https://github.com/uzivatel/nazev-appky.git /var/www/nazev-appky
cd /var/www/nazev-appky
```

### Krok 2 — Python prostředí
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Každá appka má izolované balíčky ve vlastním venv — nekonfliktují mezi sebou.

### Krok 3 — Konfigurace (.env)

Generování SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Generování PASSWORD_HASH:
```bash
source venv/bin/activate
python3 setup.py
# zadej heslo → zkopíruj hash
```

Vytvoření .env:
```bash
cat > /var/www/nazev-appky/.env << 'EOF'
SECRET_KEY=SEM_VLOZ_VYGENEROVANY_KLIC
PASSWORD_HASH=SEM_VLOZ_HASH
DATABASE_URL=sqlite:///./databaze.db
UPLOAD_DIR=uploads
EOF
```

Osobní a firemní údaje se nastavují v aplikaci na stránce Profil (`/profil`), nikoliv v .env.

### Krok 4 — Migrace databáze
```bash
source venv/bin/activate
python migrate.py
```

Tabulky se vytvoří automaticky při prvním startu. Migrace přidá chybějící sloupce do existující DB — je idempotentní, lze spouštět opakovaně.

### Krok 5 — Systemd service

Porty — každá appka jiný port:
- appka1 → 8001
- appka2 → 8002
- ...

```bash
cat > /etc/systemd/system/nazev-appky.service << EOF
[Unit]
Description=Nazev Appky
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/nazev-appky
Environment="PATH=/var/www/nazev-appky/venv/bin"
ExecStart=/var/www/nazev-appky/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 800X
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nazev-appky
systemctl start nazev-appky
systemctl status nazev-appky
```

### Krok 6 — Nginx reverse proxy
```bash
cat > /etc/nginx/sites-available/nazev-appky << 'EOF'
server {
    listen 80;
    server_name appka1.tvadomena.cz;
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:800X;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/nazev-appky /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Krok 7 — SSL certifikát (HTTPS zdarma)
```bash
certbot --nginx -d appka1.tvadomena.cz
```

Certbot se automaticky obnovuje přes systemd timer. Ověření:
```bash
certbot renew --dry-run
```

---

## 5. Automatický deploy (GitHub Actions)

Místo ručního `git pull` na serveru lze nastavit auto-deploy při push do `main`.

### Předpoklady
- SSH klíč vygenerovaný pro deploy (`ssh-keygen -t ed25519`)
- Veřejný klíč přidaný do `~/.ssh/authorized_keys` na serveru
- V GitHub repo Settings → Secrets and variables → Actions přidat:

| Secret | Hodnota |
|---|---|
| `SERVER_HOST` | IP adresa serveru |
| `SERVER_USER` | `root` (nebo deploy uživatel) |
| `SERVER_SSH_KEY` | Obsah privátního klíče |

### Workflow soubor (.github/workflows/deploy.yml)
```yaml
name: Deploy to production

on:
  push:
    branches: [main]
    tags: ["v*"]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /var/www/nazev-appky
            git pull
            git fetch --tags
            git describe --tags --abbrev=0 > VERSION 2>/dev/null || echo "dev" > VERSION
            source venv/bin/activate
            pip install -r requirements.txt --quiet
            python migrate.py
            systemctl restart nazev-appky
```

### Verzování
```bash
git tag v1.0.0
git push --tags
```

Verze se zapíše do souboru `VERSION` na serveru a zobrazí se v aplikaci.

---

## 6. Zálohy

### Backup script (na serveru, ne v repu)

Vytvořit `/root/backup-nazev-appky.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="/root/backups/nazev-appky"
DATE=$(date +%Y%m%d_%H%M)
mkdir -p "$BACKUP_DIR"
sqlite3 /var/www/nazev-appky/databaze.db ".backup $BACKUP_DIR/databaze_${DATE}.db"
[ -d /var/www/nazev-appky/uploads ] && [ "$(ls -A /var/www/nazev-appky/uploads 2>/dev/null)" ] && tar czf "$BACKUP_DIR/uploads_${DATE}.tar.gz" -C /var/www/nazev-appky uploads
find "$BACKUP_DIR" -name "databaze_*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +30 -delete
echo "[$(date)] Backup OK"
```

```bash
chmod +x /root/backup-nazev-appky.sh
```

### Cron (denně ve 3:00)
```bash
(crontab -l 2>/dev/null; echo "0 3 * * * /root/backup-nazev-appky.sh >> /var/log/nazev-appky-backup.log 2>&1") | crontab -
```

### Kontrola záloh
```bash
ls -lht /root/backups/nazev-appky/ | head -10
du -sh /root/backups/nazev-appky/
tail -5 /var/log/nazev-appky-backup.log
```

Zálohy starší 30 dní se mažou automaticky. SQLite se zálohuje přes `.backup` (bezpečné i za běhu appky).

---

## 7. Struktura na serveru

```
/var/www/
  nazev-appky/
    app/
    venv/
    .env              ← nikdy do Gitu!
    faktury.db        ← SQLite databáze
    uploads/          ← přílohy
    requirements.txt
    VERSION           ← zapisuje deploy pipeline
  dalsi-appka/
    ...

/root/
  backups/
    nazev-appky/
      databaze_20260320_0300.db
      uploads_20260320_0300.tar.gz
  backup-nazev-appky.sh
```

---

## 8. Užitečné příkazy

### Status a logy
```bash
systemctl status nazev-appky            # stav služby
journalctl -u nazev-appky -f            # live logy
journalctl -u nazev-appky -n 50         # posledních 50 řádků
```

### Nginx
```bash
nginx -t                                # test konfigurace
systemctl restart nginx
```

### SSL certifikáty
```bash
certbot certificates                    # přehled certifikátů a platnosti
certbot renew --dry-run                 # test obnovy
```

### Databáze
```bash
sqlite3 /var/www/nazev-appky/faktury.db ".tables"      # výpis tabulek
sqlite3 /var/www/nazev-appky/faktury.db ".schema"       # schéma
```

### Disk a zálohy
```bash
df -h /                                 # volné místo
du -sh /root/backups/                   # velikost záloh
crontab -l                              # naplánované úlohy
```

---

## 9. .gitignore

```
.env
*.db
*.db-shm
*.db-wal
venv/
uploads/
__pycache__/
*.pyc
VERSION
```
