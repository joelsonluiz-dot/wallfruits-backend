# ⚡ Comandos Rápidos - Deploy VPS

## 🎯 Deploy em 3 passos (cola tudo de uma vez)

### 1️⃣ No seu PC Windows (enviar código)
```powershell
# Opção A: Via SCP
cd C:\Users\User\Desktop
scp -r wallfruits-backend root@SEU_IP_VPS:/opt/

# Opção B: Commit e push no Git
cd C:\Users\User\Desktop\wallfruits-backend
git add .
git commit -m "Deploy production"
git push origin main
```

### 2️⃣ No VPS (instalar tudo)
```bash
# Conectar
ssh root@SEU_IP_VPS

# Instalar dependências (cola tudo)
sudo apt update && sudo apt install -y git docker.io docker-compose-plugin nginx certbot python3-certbot-nginx && sudo systemctl enable --now docker

# Se enviou via SCP
cd /opt/wallfruits-backend

# OU se usou Git
cd /opt && git clone https://github.com/SEU_USER/wallfruits-backend.git && cd wallfruits-backend
```

### 3️⃣ Configurar e subir
```bash
# Gerar SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Editar .env (cole a chave gerada acima)
nano .env
# Mude: SECRET_KEY=COLE_AQUI
# Mude: CORS_ORIGINS=["https://seudominio.com"]
# Mude: ALLOWED_HOSTS=["seudominio.com"]
# Ctrl+O, Enter, Ctrl+X

# Subir tudo
docker compose -f docker-compose.prod.yml up -d --build

# Testar
curl http://localhost:8000/health
```

---

## 🌐 Configurar domínio e HTTPS (opcional mas recomendado)

```bash
# Criar config Nginx
sudo nano /etc/nginx/sites-available/wallfruits
```

Cole (troque `seudominio.com`):
```nginx
server {
    listen 80;
    server_name seudominio.com www.seudominio.com;
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ativar:
```bash
sudo ln -s /etc/nginx/sites-available/wallfruits /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Firewall
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw --force enable

# HTTPS
sudo certbot --nginx -d seudominio.com -d www.seudominio.com
```

Pronto! Acesse: `https://seudominio.com/health`

---

## 📦 Atualizar código depois

```bash
cd /opt/wallfruits-backend
git pull  # ou envie via scp de novo
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 🔧 Comandos úteis

```bash
# Ver logs
docker compose -f docker-compose.prod.yml logs -f api

# Reiniciar
docker compose -f docker-compose.prod.yml restart

# Parar
docker compose -f docker-compose.prod.yml down

# Status
docker compose -f docker-compose.prod.yml ps

# Backup banco
docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres wallfruits_db > backup.sql
```

---

## ✅ URLs finais

- API Docs: `https://seudominio.com/docs`
- Testes QA: `https://seudominio.com/qa`
- Health: `https://seudominio.com/health`
