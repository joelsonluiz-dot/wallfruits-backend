# 🚀 Deploy WallFruits Backend em VPS Linux

## Pré-requisitos
- VPS Ubuntu 20.04/22.04 (mínimo 2GB RAM)
- IP público do VPS
- Domínio apontado para o IP (opcional mas recomendado)
- Acesso SSH root ou sudo

---

## PARTE 1: Preparar VPS (copie e cole no SSH)

### 1.1 Conectar no VPS
```bash
ssh root@SEU_IP_VPS
# ou
ssh usuario@SEU_IP_VPS
```

### 1.2 Atualizar sistema e instalar dependências
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl docker.io docker-compose-plugin nginx certbot python3-certbot-nginx ufw
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

**IMPORTANTE**: Depois de `usermod`, deslogue e logue novamente no SSH:
```bash
exit
ssh root@SEU_IP_VPS
```

### 1.3 Verificar Docker instalado
```bash
docker --version
docker compose version
```

---

## PARTE 2: Enviar código para VPS

### Opção A: Via Git (RECOMENDADO)
```bash
cd /opt
sudo git clone https://github.com/SEU_USUARIO/wallfruits-backend.git
sudo chown -R $USER:$USER wallfruits-backend
cd wallfruits-backend
```

### Opção B: Via SCP (do seu PC Windows)
No PowerShell do seu PC:
```powershell
cd C:\Users\User\Desktop
scp -r wallfruits-backend root@SEU_IP_VPS:/opt/
```

Depois no VPS:
```bash
cd /opt/wallfruits-backend
```

---

## PARTE 3: Configurar variáveis de ambiente

```bash
nano .env
```

**Edite estas linhas OBRIGATORIAMENTE:**

```env
# Banco de dados (mantenha assim, Docker Compose cria automaticamente)
DATABASE_URL=postgresql://postgres:postgres@db:5432/wallfruits_db

# MUDE ESTA CHAVE AGORA (gere uma forte)
SECRET_KEY=COLE_AQUI_UMA_CHAVE_SECRETA_LONGA_E_ALEATORIA

# Seu domínio ou IP
CORS_ORIGINS=["https://seudominio.com","http://SEU_IP_VPS:8000"]
ALLOWED_HOSTS=["seudominio.com","www.seudominio.com","SEU_IP_VPS"]

# Redis (mantenha assim)
REDIS_ENABLED=true
REDIS_URL=redis://redis:6379/0

# Produção
DEBUG=false
LOG_LEVEL=INFO
```

**Gerar SECRET_KEY forte:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copie o resultado e cole no `SECRET_KEY=...`

Salve com `Ctrl+O`, Enter, `Ctrl+X`.

---

## PARTE 4: Subir aplicação com Docker

```bash
cd /opt/wallfruits-backend

# Subir todos os containers (PostgreSQL, Redis, API)
docker compose -f docker-compose.prod.yml up -d --build

# Ver status
docker compose -f docker-compose.prod.yml ps

# Ver logs
docker compose -f docker-compose.prod.yml logs -f api
```

Pressione `Ctrl+C` para sair dos logs.

### Testar se está funcionando
```bash
curl http://localhost:8000/health
```

Deve retornar:
```json
{"status":"ok","version":"2.0.0","environment":"production"}
```

---

## PARTE 5: Configurar Nginx (proxy reverso + HTTPS)

### 5.1 Criar configuração Nginx
```bash
sudo nano /etc/nginx/sites-available/wallfruits
```

Cole isto (TROQUE `seudominio.com`):

```nginx
server {
    listen 80;
    server_name seudominio.com www.seudominio.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Salve (`Ctrl+O`, Enter, `Ctrl+X`).

### 5.2 Ativar site e reiniciar Nginx
```bash
sudo ln -s /etc/nginx/sites-available/wallfruits /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5.3 Configurar Firewall
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

---

## PARTE 6: Habilitar HTTPS com Let's Encrypt

```bash
sudo certbot --nginx -d seudominio.com -d www.seudominio.com
```

Siga as instruções:
- Digite seu email
- Aceite os termos (Y)
- Escolha redirecionar HTTP para HTTPS (opção 2)

Renovação automática já está configurada.

---

## PARTE 7: Testar tudo funcionando

### No navegador:
```
https://seudominio.com/health
https://seudominio.com/docs
https://seudominio.com/qa
```

### Via curl:
```bash
curl https://seudominio.com/health
```

---

## 📊 Comandos úteis de manutenção

```bash
# Ver logs em tempo real
docker compose -f docker-compose.prod.yml logs -f

# Reiniciar API
docker compose -f docker-compose.prod.yml restart api

# Parar tudo
docker compose -f docker-compose.prod.yml down

# Reiniciar tudo
docker compose -f docker-compose.prod.yml restart

# Atualizar código e rebuild
git pull
docker compose -f docker-compose.prod.yml up -d --build

# Ver uso de recursos
docker stats

# Acessar banco de dados
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d wallfruits_db

# Backup do banco
docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres wallfruits_db > backup_$(date +%Y%m%d).sql
```

---

## 🔒 Segurança adicional (RECOMENDADO)

### Desabilitar login root SSH
```bash
sudo nano /etc/ssh/sshd_config
# Mude: PermitRootLogin no
sudo systemctl restart sshd
```

### Limitar tentativas de login
```bash
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban
```

---

## ❌ Troubleshooting

### API não responde
```bash
docker compose -f docker-compose.prod.yml logs api
# Ver se há erros de conexão com DB ou Redis
```

### Banco de dados não conecta
```bash
docker compose -f docker-compose.prod.yml ps
# Verificar se container 'wallfruits-db' está rodando
docker compose -f docker-compose.prod.yml logs db
```

### Nginx erro 502
```bash
# Verificar se API está rodando
curl http://localhost:8000/health

# Ver logs do Nginx
sudo tail -f /var/log/nginx/error.log
```

### Resetar banco de dados
```bash
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d
```

---

## ✅ Checklist final

- [ ] VPS acessível via SSH
- [ ] Docker e Docker Compose instalados
- [ ] Código enviado para `/opt/wallfruits-backend`
- [ ] `.env` configurado com SECRET_KEY forte
- [ ] `docker compose up -d` executado sem erros
- [ ] `curl http://localhost:8000/health` retorna OK
- [ ] Nginx configurado e rodando
- [ ] Firewall habilitado (80, 443, 22)
- [ ] SSL/HTTPS configurado com Certbot
- [ ] `https://seudominio.com/health` acessível no navegador

---

**Pronto! Seu sistema está no ar para usuários finais testarem.**
