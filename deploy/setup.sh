#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SSA Monitor Processos — Script de instalação para Ubuntu 22.04 / 24.04
# Hostinger VPS ou qualquer Ubuntu/Debian com acesso root
#
# Uso:
#   chmod +x setup.sh
#   sudo ./setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

APP_DIR="/opt/ssa-monitor"
APP_USER="ssa"
PYTHON_MIN="3.11"

echo "========================================"
echo " SSA Monitor Processos — Setup"
echo "========================================"

# 1. Atualiza sistema
echo "[1/8] Atualizando pacotes..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2
# libasound2 foi renomeado para libasound2t64 no Ubuntu 24.04
apt-get install -y -qq libasound2t64 2>/dev/null || apt-get install -y -qq libasound2 2>/dev/null || true

# 2. Cria usuário de serviço (sem login)
echo "[2/8] Criando usuário '$APP_USER'..."
id -u "$APP_USER" &>/dev/null || useradd -r -s /bin/false -m "$APP_USER"
mkdir -p "/home/$APP_USER"
chown "$APP_USER":"$APP_USER" "/home/$APP_USER"

# 3. Cria diretório da aplicação
echo "[3/8] Configurando diretório $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

# 4. Cria ambiente virtual Python
echo "[4/8] Criando ambiente virtual..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip -q
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q

# 5. Instala Playwright + Chromium
echo "[5/8] Instalando Chromium (Playwright)..."
"$APP_DIR/.venv/bin/playwright" install chromium
"$APP_DIR/.venv/bin/playwright" install-deps chromium

# 6. Configura .env
echo "[6/8] Configurando variáveis de ambiente..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo "  ⚠️  ATENÇÃO: preencha as variáveis em $APP_DIR/.env antes de iniciar!"
    echo ""
fi

# 7. Instala serviços systemd
echo "[7/8] Instalando serviços systemd..."
cp "$APP_DIR/deploy/ssa-dashboard.service" /etc/systemd/system/
cp "$APP_DIR/deploy/ssa-monitor.service"   /etc/systemd/system/
systemctl daemon-reload
systemctl enable ssa-dashboard
systemctl enable ssa-monitor

# 8. Configura logrotate
echo "[8/8] Configurando rotação de logs..."
cat > /etc/logrotate.d/ssa-monitor << 'EOF'
/var/log/ssa-monitor/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 ssa ssa
}
EOF
mkdir -p /var/log/ssa-monitor
chown "$APP_USER":"$APP_USER" /var/log/ssa-monitor

echo ""
echo "========================================"
echo " Instalação concluída!"
echo "========================================"
echo ""
echo " Próximos passos:"
echo "  1. Edite $APP_DIR/.env com os dados do banco e API key"
echo "  2. sudo systemctl start ssa-dashboard"
echo "  3. sudo systemctl start ssa-monitor"
echo "  4. Dashboard disponível em: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
