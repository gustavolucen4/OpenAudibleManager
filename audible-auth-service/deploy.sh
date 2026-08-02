#!/bin/bash
# =============================================================================
# OpenAudible Manager — Deploy Script (Linux Server)
# =============================================================================
# Rebuilds and restarts the Docker container with the latest code.
# Run this from the audible-auth-service directory on the Linux server.
# =============================================================================

set -e

echo "🛑 Parando container atual..."
docker compose down || true

echo "🗑️  Removendo imagem antiga para forçar rebuild completo..."
docker rmi openaudible-manager:latest 2>/dev/null || true

echo "🔨 Reconstruindo imagem com o código mais recente..."
docker compose build --no-cache

echo "🚀 Subindo o container..."
docker compose up -d

echo ""
echo "✅ Deploy concluído!"
echo "📋 Logs em tempo real (Ctrl+C para sair):"
echo ""
docker compose logs -f --tail=50
