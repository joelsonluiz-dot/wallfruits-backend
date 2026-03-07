# 🎁 Oracle Cloud - VPS GRÁTIS Para Sempre

## ✅ O que você ganha de GRAÇA permanentemente:
- **2 VMs** com 1 GB RAM cada (AMD)
- **OU 1 VM** com 4 CPUs + 24 GB RAM (ARM - RECOMENDADO!)
- **200 GB** de armazenamento
- **10 TB** de tráfego por mês
- **Válido para sempre** (não expira)

---

## 📍 PASSO 1: Criar conta Oracle Cloud

### 1.1 Acessar
https://www.oracle.com/cloud/free/

### 1.2 Clicar em "Start for free" ou "Começar gratuitamente"

### 1.3 Preencher dados
- **País/Território**: Brazil
- **Nome**: Seu nome completo
- **Email**: Seu email (vai receber verificação)
- **Senha**: Crie uma senha forte

### 1.4 Verificar email
- Abra o email da Oracle
- Clique no link de verificação

### 1.5 Preencher informações adicionais
- **Endereço**: Seu endereço real
- **Telefone**: Seu celular (vai receber SMS)
- **Tipo de conta**: Selecione "Individual" (pessoal)

### 1.6 Verificação de cartão
⚠️ **IMPORTANTE**: Pede cartão mas **NÃO COBRA NADA**!
- É só para verificar que você é real
- Aceita cartão de débito ou crédito
- Eles fazem verificação de R$1-5 que é devolvida
- Nunca vai cobrar nada enquanto você usar só o Free Tier

### 1.7 Aguardar aprovação
- Pode demorar de 5 minutos a 2 horas
- Você recebe email quando estiver pronta

---

## 📍 PASSO 2: Criar VM (Servidor Virtual)

### 2.1 Login no Oracle Cloud
https://cloud.oracle.com/

### 2.2 No Dashboard, clicar em "Create a VM instance"
Ou Menu (☰) → Compute → Instances → Create Instance

### 2.3 Configurar a VM

#### Nome
```
wallfruits-server
```

#### Compartment
- Deixe o padrão (root)

#### Placement
- Deixe o padrão

#### Image and Shape
**CLIQUE EM "EDIT" na seção Shape**

**Shape:**
- Clique em "Change Shape"
- Selecione: **Ampere (ARM)** - VM.Standard.A1.Flex
- CPUs: **4** (máximo grátis)
- Memory: **24 GB** (máximo grátis)
- Clique "Select Shape"

**Image:**
- Deixe "Canonical Ubuntu" (22.04 ou 20.04)
- OU clique "Change Image" → Canonical Ubuntu → 22.04

#### Networking
- Deixe "Create new virtual cloud network"
- Deixe "Assign a public IPv4 address" ✅ MARCADO

#### Add SSH keys
**IMPORTANTE** - Você precisa de uma chave SSH:

**No seu PC Windows, abra PowerShell e cole:**
```powershell
ssh-keygen -t rsa -b 4096 -f "$env:USERPROFILE\.ssh\oracle_cloud_key"
```

Pressione Enter 3 vezes (sem senha).

Agora veja a chave pública:
```powershell
Get-Content "$env:USERPROFILE\.ssh\oracle_cloud_key.pub"
```

**Copie TODO o texto** que aparecer (começa com `ssh-rsa`).

Volte no navegador (Oracle Cloud):
- Deixe "Paste public keys" selecionado
- Cole a chave que você copiou
- OU clique "Choose public key file" e selecione `C:\Users\User\.ssh\oracle_cloud_key.pub`

#### Boot Volume
- Deixe padrão (200 GB grátis)

### 2.4 Clicar em "Create" (criar)

Aguarde 2-5 minutos. A VM vai aparecer como "Running" (rodando).

### 2.5 Anotar o IP público
Na tela da instância, procure:
```
Public IP address: 140.238.123.45 (exemplo)
```

**ANOTE ESTE IP!** Você vai usar sempre.

---

## 📍 PASSO 3: Configurar Firewall (IMPORTANTE!)

Oracle Cloud bloqueia tudo por padrão. Precisa liberar portas:

### 3.1 Na página da VM, rolar até "Primary VNIC"
Clique no nome da subnet (ex: "subnet-xxxxx")

### 3.2 Clicar em "Security Lists"
Clique no security list que aparece (ex: "Default Security List...")

### 3.3 Adicionar regras de entrada
Clique em "Add Ingress Rules"

**Regra 1 - HTTP:**
- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `80`
- Clique "Add Ingress Rules"

**Regra 2 - HTTPS:**
- Clique "Add Ingress Rules" de novo
- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `443`
- Clique "Add Ingress Rules"

**Regra 3 - API (temporária para testes):**
- Clique "Add Ingress Rules" de novo
- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `8000`
- Clique "Add Ingress Rules"

---

## 📍 PASSO 4: Conectar na VM via SSH

### 4.1 No PowerShell do Windows:
```powershell
ssh -i "$env:USERPROFILE\.ssh\oracle_cloud_key" ubuntu@140.238.123.45
```

**Troque `140.238.123.45` pelo seu IP real!**

Se pedir confirmação, digite `yes` e Enter.

### 4.2 Você está dentro da VM!
Deve aparecer algo como:
```
ubuntu@wallfruits-server:~$
```

### 4.3 Liberar firewall do Ubuntu também
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save
```

---

## 📍 PASSO 5: Enviar código para a VM

### Opção A: Via SCP (do seu PC)

**No PowerShell do Windows:**
```powershell
cd C:\Users\User\Desktop
scp -i "$env:USERPROFILE\.ssh\oracle_cloud_key" -r wallfruits-backend ubuntu@140.238.123.45:/home/ubuntu/
```

**Na VM (SSH):**
```bash
sudo mv /home/ubuntu/wallfruits-backend /opt/
sudo chown -R ubuntu:ubuntu /opt/wallfruits-backend
cd /opt/wallfruits-backend
```

### Opção B: Via Git (recomendado)

**No seu PC, commit no Git:**
```powershell
cd C:\Users\User\Desktop\wallfruits-backend
git init
git add .
git commit -m "Deploy Oracle Cloud"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/wallfruits-backend.git
git push -u origin main
```

**Na VM (SSH):**
```bash
cd /opt
sudo git clone https://github.com/SEU_USUARIO/wallfruits-backend.git
sudo chown -R ubuntu:ubuntu wallfruits-backend
cd wallfruits-backend
```

---

## 📍 PASSO 6: Instalar Docker e subir aplicação

**Na VM, cole tudo de uma vez:**

```bash
# Instalar Docker
sudo apt update
sudo apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
```

**Deslogue e logue novamente:**
```bash
exit
```

```powershell
# Do Windows, conecte de novo:
ssh -i "$env:USERPROFILE\.ssh\oracle_cloud_key" ubuntu@140.238.123.45
```

**Agora configure e suba:**

```bash
cd /opt/wallfruits-backend

# Gerar SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Editar .env
nano .env
```

**No nano, edite:**
- `SECRET_KEY=` cole a chave gerada acima
- `CORS_ORIGINS=["http://140.238.123.45:8000"]` (use seu IP)
- `ALLOWED_HOSTS=["140.238.123.45"]` (use seu IP)

Salve: `Ctrl+O`, Enter, `Ctrl+X`

**Subir aplicação:**
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

**Aguardar 30 segundos e testar:**
```bash
curl http://localhost:8000/health
```

---

## 📍 PASSO 7: Testar do seu PC

**No navegador:**
```
http://140.238.123.45:8000/health
http://140.238.123.45:8000/docs
http://140.238.123.45:8000/qa
```

**Troque pelo seu IP real!**

---

## 🌐 EXTRA: Configurar domínio grátis (opcional)

Use **DuckDNS** (grátis):

1. Acesse: https://www.duckdns.org/
2. Login com Google/GitHub
3. Crie um subdomínio: `wallfruits.duckdns.org`
4. Aponte para o IP da VM: `140.238.123.45`
5. Copie o token

**Na VM:**
```bash
# Instalar cliente DuckDNS
echo "*/5 * * * * curl 'https://www.duckdns.org/update?domains=wallfruits&token=SEU_TOKEN&ip=' >/dev/null 2>&1" | crontab -

# Configurar Nginx
sudo nano /etc/nginx/sites-available/wallfruits
```

Cole:
```nginx
server {
    listen 80;
    server_name wallfruits.duckdns.org;
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

Salve e ative:
```bash
sudo ln -s /etc/nginx/sites-available/wallfruits /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Configurar HTTPS
sudo certbot --nginx -d wallfruits.duckdns.org
```

Agora acesse: `https://wallfruits.duckdns.org/health`

---

## 📊 Comandos úteis

```bash
# Conectar na VM
ssh -i "$env:USERPROFILE\.ssh\oracle_cloud_key" ubuntu@SEU_IP

# Ver logs
docker compose -f docker-compose.prod.yml logs -f

# Reiniciar
docker compose -f docker-compose.prod.yml restart

# Parar
docker compose -f docker-compose.prod.yml down

# Atualizar código
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

---

## ⚠️ Troubleshooting

### Não consigo conectar via SSH
```powershell
# Verificar se a chave existe
Test-Path "$env:USERPROFILE\.ssh\oracle_cloud_key"

# Ajustar permissões (pode ser necessário)
icacls "$env:USERPROFILE\.ssh\oracle_cloud_key" /inheritance:r
icacls "$env:USERPROFILE\.ssh\oracle_cloud_key" /grant:r "$env:USERNAME:(R)"
```

### Não consigo acessar HTTP/HTTPS no navegador
1. Verificar se liberou portas no Security List (Passo 3)
2. Verificar se rodou os comandos iptables (Passo 4.3)
3. Verificar se API está rodando: `docker compose ps`

### VM "Out of Capacity"
Tente outra região:
- Menu → Governance → Region Management
- Clique em "Subscribe" em outra região
- Tente criar VM lá

Regiões com mais disponibilidade:
- São Paulo (South America East)
- Chile (Santiago)
- Ashburn (US East)

---

## ✅ Checklist final

- [ ] Conta Oracle Cloud criada e aprovada
- [ ] VM criada com 4 CPUs e 24 GB RAM (ARM)
- [ ] IP público anotado
- [ ] Portas 80, 443, 8000 liberadas no Security List
- [ ] Firewall Ubuntu configurado (iptables)
- [ ] Chave SSH criada (`oracle_cloud_key`)
- [ ] Conectado via SSH
- [ ] Código enviado via SCP ou Git
- [ ] Docker instalado
- [ ] `.env` configurado com SECRET_KEY
- [ ] `docker compose up -d` executado
- [ ] `http://SEU_IP:8000/health` acessível

---

**Pronto! Servidor 100% grátis rodando na Oracle Cloud! 🎉**

Precisa de ajuda em algum passo? Me avisa!
