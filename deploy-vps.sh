#!/bin/bash
#
# Script automatico de deploy WallFruits Backend em VPS Ubuntu
# Uso: bash deploy-vps.sh
#

set -e

echo "========================================"
echo " WALLFRUITS - Deploy Automatico VPS"
echo "========================================"
echo ""

# Verificar se esta rodando como root ou com sudo
if [[ $EUID -ne 0 ]]; then
   echo "Este script precisa ser executado como root ou com sudo"
   exit 1
fi

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função de log
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Atualizar sistema
log_info "Atualizando sistema..."
apt update && apt upgrade -y

# 2. Instalar dependencias
log_info "Instalando Docker, Docker Compose, Nginx, Certbot..."
apt install -y git curl docker.io docker-compose-plugin nginx certbot python3-certbot-nginx ufw

# 3. Habilitar Docker
systemctl enable --now docker
log_info "Docker habilitado e rodando"

# 4. Criar diretorio de deploy
DEPLOY_DIR="/opt/wallfruits-backend"
if [ -d "$DEPLOY_DIR" ]; then
    log_warn "Diretorio $DEPLOY_DIR ja existe. Pulando clone."
else
    log_info "Codigo deve ser clonado ou copiado para $DEPLOY_DIR"
    mkdir -p $DEPLOY_DIR
fi

cd $DEPLOY_DIR

# 5. Verificar .env
if [ ! -f ".env" ]; then
    log_error "Arquivo .env nao encontrado em $DEPLOY_DIR"
    log_info "Crie o arquivo .env com as configuracoes necessarias antes de continuar"
    exit 1
fi

# 6. Verificar SECRET_KEY
if grep -q "SECRET_KEY=CHANGE_ME" .env; then
    log_error "SECRET_KEY ainda esta com valor padrao! Altere no .env"
    exit 1
fi

# 7. Subir containers
log_info "Subindo containers com Docker Compose..."
docker compose -f docker-compose.prod.yml up -d --build

# 8. Aguardar API iniciar
log_info "Aguardando API inicializar (10 segundos)..."
sleep 10

# 9. Testar health check
log_info "Testando health check..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    log_info "API respondendo corretamente!"
else
    log_error "API nao esta respondendo. Verifique os logs:"
    docker compose -f docker-compose.prod.yml logs api
    exit 1
fi

# 10. Configurar Firewall
log_info "Configurando firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable

# 11. Perguntar sobre dominio
echo ""
read -p "Voce tem um dominio configurado? (s/n): " tem_dominio

if [[ $tem_dominio == "s" || $tem_dominio == "S" ]]; then
    read -p "Digite o dominio (ex: wallfruits.com): " DOMAIN
    
    # Criar config Nginx
    log_info "Criando configuracao Nginx para $DOMAIN..."
    cat > /etc/nginx/sites-available/wallfruits <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

    # Ativar site
    ln -sf /etc/nginx/sites-available/wallfruits /etc/nginx/sites-enabled/
    nginx -t && systemctl restart nginx
    
    log_info "Nginx configurado para $DOMAIN"
    
    # Perguntar sobre SSL
    read -p "Configurar HTTPS com Let's Encrypt? (s/n): " config_ssl
    
    if [[ $config_ssl == "s" || $config_ssl == "S" ]]; then
        read -p "Digite seu email: " EMAIL
        certbot --nginx -d $DOMAIN -d www.$DOMAIN --email $EMAIL --agree-tos --no-eff-email --redirect
        log_info "HTTPS configurado com sucesso!"
    fi
else
    log_warn "Aplicacao rodando apenas em http://SEU_IP:8000"
    log_warn "Para acesso externo, configure Nginx manualmente depois"
fi

# 12. Status final
echo ""
echo "========================================"
log_info "Deploy concluido com sucesso!"
echo "========================================"
echo ""
log_info "Status dos containers:"
docker compose -f docker-compose.prod.yml ps
echo ""
log_info "Comandos uteis:"
echo "  - Ver logs: docker compose -f docker-compose.prod.yml logs -f"
echo "  - Reiniciar: docker compose -f docker-compose.prod.yml restart"
echo "  - Parar: docker compose -f docker-compose.prod.yml down"
echo ""

if [[ $tem_dominio == "s" || $tem_dominio == "S" ]]; then
    if [[ $config_ssl == "s" || $config_ssl == "S" ]]; then
        log_info "Acesse: https://$DOMAIN/health"
    else
        log_info "Acesse: http://$DOMAIN/health"
    fi
fi

log_info "Documentacao API: /docs"
log_info "Interface de testes: /qa"
echo ""
