# Deploy — SSA Monitor Processos no Hostinger VPS

## Pré-requisitos no servidor

- Ubuntu 22.04 ou 24.04 (VPS Hostinger)
- Python 3.11+
- MySQL 8.0+ (pode ser o banco do próprio Hostinger ou um VPS dedicado)
- Acesso root via SSH

---

## 1. Enviar os arquivos para o servidor

```bash
# Na sua máquina Windows (PowerShell):
scp -r "C:\Automacao_Python\Automações_gerais\SsaMonitorProcessos" root@IP_DO_SERVIDOR:/tmp/ssa-monitor

# Ou usar Git (recomendado):
git clone https://github.com/seu-usuario/ssa-monitor.git /tmp/ssa-monitor
```

---

## 2. Executar o script de instalação

```bash
ssh root@IP_DO_SERVIDOR
cd /tmp/ssa-monitor
chmod +x deploy/setup.sh
sudo ./deploy/setup.sh
```

O script instala automaticamente:
- Dependências do sistema
- Python e ambiente virtual
- Playwright + Chromium
- Serviços systemd

---

## 3. Configurar o .env

```bash
sudo nano /opt/ssa-monitor/.env
```

Preencha:
```
DB_HOST=localhost          # ou IP do banco remoto
DB_USER=ssa_user
DB_PASSWORD=SENHA_SEGURA
DB_NAME=ssa_monitor_processos
CAPTCHA_API_KEY=SUA_CHAVE_2CAPTCHA
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8000
```

---

## 4. Criar o banco de dados MySQL

```bash
mysql -u root -p << 'SQL'
CREATE DATABASE ssa_monitor_processos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ssa_user'@'localhost' IDENTIFIED BY 'SENHA_SEGURA';
GRANT ALL PRIVILEGES ON ssa_monitor_processos.* TO 'ssa_user'@'localhost';
FLUSH PRIVILEGES;
SQL
```

---

## 5. Iniciar os serviços

```bash
sudo systemctl start ssa-dashboard
sudo systemctl start ssa-monitor

# Verificar status:
sudo systemctl status ssa-dashboard
sudo systemctl status ssa-monitor

# Ver logs em tempo real:
sudo tail -f /var/log/ssa-monitor/dashboard.log
sudo tail -f /var/log/ssa-monitor/monitor.log
```

---

## 6. Configurar Nginx (acesso pelo domínio)

```bash
sudo apt-get install -y nginx
sudo cp /opt/ssa-monitor/deploy/nginx-ssa.conf /etc/nginx/sites-available/ssa-monitor
# Edite o server_name com seu domínio:
sudo nano /etc/nginx/sites-available/ssa-monitor
sudo ln -s /etc/nginx/sites-available/ssa-monitor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### SSL gratuito com Let's Encrypt:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d seu-dominio.com.br
```

---

## 7. Abrir porta no firewall (se necessário)

```bash
sudo ufw allow 8000/tcp   # acesso direto (sem nginx)
sudo ufw allow 80/tcp     # com nginx HTTP
sudo ufw allow 443/tcp    # com nginx HTTPS
sudo ufw enable
```

---

## Comandos úteis

| Ação | Comando |
|------|---------|
| Reiniciar dashboard | `sudo systemctl restart ssa-dashboard` |
| Reiniciar monitor | `sudo systemctl restart ssa-monitor` |
| Ver logs dashboard | `sudo journalctl -u ssa-dashboard -f` |
| Ver logs monitor | `sudo journalctl -u ssa-monitor -f` |
| Parar tudo | `sudo systemctl stop ssa-dashboard ssa-monitor` |
| Atualizar código | `cd /opt/ssa-monitor && git pull && sudo systemctl restart ssa-dashboard ssa-monitor` |

---

## Estrutura de logs

```
/var/log/ssa-monitor/
├── dashboard.log   # logs do servidor web
└── monitor.log     # logs das consultas automáticas
```
