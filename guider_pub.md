# VPS Průvodce — Python appky na vlastním serveru

## 1. Infrastruktura

### Server
- **Poskytovatel:** Hetzner Cloud (doporučeno)
- **Typ:** CAX11 nebo CX23 (2 vCPU, 4 GB RAM, 40 GB SSD)
- **Cena:** ~€3.50–4.00/měsíc
- **OS:** Ubuntu 24.04
- **Přihlášení:** `ssh uzivatel@IP_SERVERU`

### Doména
- **Poskytovatel:** Wedos, Forpsi nebo jiný czech registrátor
- **Propojení:** A záznamy v DNS ukazují na IP serveru
- **Doporučená struktura:** jedna hlavní doména + subdomény pro každou appku

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
apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx
```

### Uživatel (bezpečnější než běžet jako root)
```bash
adduser --disabled-password --gecos "" uzivatel
usermod -aG sudo uzivatel
mkdir -p /home/uzivatel/.ssh
cp ~/.ssh/authorized_keys /home/uzivatel/.ssh/
chown -R uzivatel:uzivatel /home/uzivatel/.ssh
```

### SSH klíč (na lokálním Macu/PC)
```bash
ssh-keygen -t ed25519 -C "vas@email.com"
cat ~/.ssh/id_ed25519.pub
# zkopíruj výstup → vlož do Hetzneru při vytváření serveru
```

---

## 4. Nasazení nové appky (opakující se postup)

### Krok 1 — Naklonuj repozitář
```bash
git clone https://github.com/uzivatel/nazev-appky.git /var/www/nazev-appky
cd /var/www/nazev-appky
```

### Krok 2 — Python prostředí (venv)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Proč venv? Každá appka má izolované balíčky — nekonfliktují mezi sebou ani se systémem.

### Krok 3 — Vytvoř .env soubor

Generování SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Generování PASSWORD_HASH (lokálně):
```bash
source venv/bin/activate
python3 setup.py
# zadej heslo → zkopíruj hash
```

Vytvoření .env na serveru:
```bash
python3 -c "
with open('/var/www/nazev-appky/.env', 'w') as f:
    f.write('OWNER_NAME=Jmeno Prijmeni\n')
    f.write('OWNER_EMAIL=vas@email.com\n')
    f.write('SECRET_KEY=SEM_VLOZ_VYGENEROVANY_KLIC\n')
    f.write('PASSWORD_HASH=SEM_VLOZ_HASH\n')
    f.write('DATABASE_URL=sqlite:///./databaze.db\n')
    f.write('UPLOAD_DIR=uploads\n')
"
```

### Krok 4 — Systemd service

Porty — každá appka jiný port:
- appka1 → 8001
- appka2 → 8002
- appka3 → 8003
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

### Krok 5 — Nginx konfigurace
```bash
cat > /etc/nginx/sites-available/nazev-appky << EOF
server {
    listen 80;
    server_name appka1.tvadomena.cz;

    location / {
        proxy_pass http://127.0.0.1:800X;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/nazev-appky /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Krok 6 — SSL certifikát (HTTPS zdarma)
```bash
certbot --nginx -d appka1.tvadomena.cz
```

Certbot se automaticky obnovuje přes systemd timer — není potřeba nic dělat ručně.

Ověření auto-obnovy:
```bash
certbot renew --dry-run
```

---

## 5. Struktura na serveru

```
/var/www/
  appka1/
    app/
    venv/
    .env          ← nikdy do Gitu!
    requirements.txt
    uploads/
  appka2/
    ...
  appka1-demo/
    ...
```

---

## 6. Development workflow

### Lokální vývoj
```bash
cd ~/Development/nazev-appky
source venv/bin/activate
uvicorn app.main:app --reload
# → http://localhost:8000
```

### Deploy na server
```bash
# 1. Lokálně — commit a push
git add .
git commit -m "feat: popis změny"
git push

# 2. Na serveru — pull a restart
cd /var/www/nazev-appky
git pull
systemctl restart nazev-appky
```

### Deploy demo verze
```bash
cd /var/www/nazev-appky-demo
git pull
systemctl restart nazev-appky-demo
```

---

## 7. Užitečné příkazy

### Status a logy
```bash
systemctl status nazev-appky
journalctl -u nazev-appky -f          # live logy
journalctl -u nazev-appky -n 50       # posledních 50 řádků
```

### Nginx
```bash
nginx -t                               # test konfigurace
systemctl restart nginx
```

### SSL certifikáty
```bash
certbot certificates                   # přehled certifikátů a platnosti
certbot renew                          # ruční obnova
certbot renew --dry-run                # test obnovy bez skutečné akce
```

---

## 8. .gitignore — co nikdy nesmí do Gitu

```
.env
*.db
*.db-shm
*.db-wal
venv/
uploads/
__pycache__/
*.pyc
```
