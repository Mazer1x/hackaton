# Повторный деплой на VPS (Windows). Из корня репозитория:
#   .\deploy\deploy-server.ps1
param(
    [string]$ServerHost = "178.72.154.235",
    [string]$User = "root",
    [string]$Key = "ssh/generator"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$KeyAbs = Join-Path $Root $Key
Set-Location $Root

Write-Host "==> bundle"
tar -czf deploy-bundle.tgz pyproject.toml Dockerfile docker-compose.yml agents deploy langgraph.json

Write-Host "==> scp"
scp -i $KeyAbs -o StrictHostKeyChecking=yes deploy-bundle.tgz "${User}@${ServerHost}:/tmp/"
if (Test-Path .env) {
    scp -i $KeyAbs -o StrictHostKeyChecking=yes .env "${User}@${ServerHost}:/tmp/dotenv-progressusbot"
}

$bash = @'
set -e
mkdir -p /opt/progressusbot /var/www/certbot
tar -xzf /tmp/deploy-bundle.tgz -C /opt/progressusbot
if [ -f /tmp/dotenv-progressusbot ]; then mv -f /tmp/dotenv-progressusbot /opt/progressusbot/.env; chmod 600 /opt/progressusbot/.env; fi
cp /opt/progressusbot/deploy/nginx-api.progressusbot.ru.conf /etc/nginx/sites-available/api.progressusbot.ru
ln -sf /etc/nginx/sites-available/api.progressusbot.ru /etc/nginx/sites-enabled/api.progressusbot.ru
nginx -t && systemctl reload nginx
cd /opt/progressusbot && docker compose build && docker compose up -d
docker compose -f /opt/progressusbot/docker-compose.yml ps
curl -sS http://127.0.0.1:8088/health
'@

Write-Host "==> remote extract + rebuild"
ssh -i $KeyAbs "${User}@${ServerHost}" $bash

Write-Host "Done. Health: https://api.progressusbot.ru/health"
