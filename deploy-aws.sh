#!/bin/sh

# Script de deployment para AWS EC2
# Uso: curl -sSL https://raw.githubusercontent.com/pintoMACRO/GestionDocumental/main/deploy-aws.sh | sh

set -e

echo "========================================="
echo "Instalando dependencias..."
echo "========================================="

# Actualizar sistema
sudo apt update
sudo apt upgrade -y

# Instalar Docker, Git y Git LFS
sudo apt install -y docker.io git curl
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash
sudo apt install -y git-lfs
git lfs install

# Habilitar Docker
sudo systemctl enable docker
sudo systemctl start docker

# Agregar usuario actual a docker group
sudo usermod -aG docker $USER

echo "✓ Dependencias instaladas"
echo ""

echo "========================================="
echo "Clonando repositorio..."
echo "========================================="

# Clonar repo limpio para evitar checkouts viejos sin binario LFS
if [ -d "GestionDocumental" ]; then
    rm -rf GestionDocumental
fi

GIT_LFS_SKIP_SMUDGE=0 git clone https://github.com/pintoMACRO/GestionDocumental.git
cd GestionDocumental

# Asegurar que el modelo grande se descargue completo
git lfs fetch --include="modelo/modelo_resnet50.keras" --all
git lfs checkout modelo/modelo_resnet50.keras
git lfs pull --include="modelo/modelo_resnet50.keras"

echo "✓ Repositorio listo"
echo ""

echo "========================================="
echo "Construyendo imagen Docker..."
echo "========================================="

# Verificar que el modelo existe y no es un puntero de Git LFS
if [ ! -f "modelo/modelo_resnet50.keras" ]; then
    echo "❌ ERROR: modelo/modelo_resnet50.keras no encontrado"
    exit 1
fi

if head -n 1 modelo/modelo_resnet50.keras | grep -q "^version https://git-lfs.github.com/spec/v1$"; then
    echo "❌ ERROR: modelo/modelo_resnet50.keras es un puntero de Git LFS, no el binario real"
    exit 1
fi

MODEL_BYTES=$(stat -c "%s" modelo/modelo_resnet50.keras)
echo "✓ Modelo encontrado (${MODEL_BYTES} bytes)"

# Build
docker build -t gestion-documental:latest .

echo "✓ Imagen construida"
echo ""

echo "========================================="
echo "Iniciando contenedor..."
echo "========================================="

# Usar sudo para docker commands
sudo docker stop gestion-documental 2>/dev/null || true
sudo docker rm gestion-documental 2>/dev/null || true
sleep 2

# Iniciar contenedor
sudo docker run -d \
    --restart unless-stopped \
    -p 8000:8000 \
    --name gestion-documental \
    --memory=2g \
    --cpus=1 \
    gestion-documental:latest

echo "✓ Contenedor iniciado"
echo ""

# Esperar a que el contenedor esté listo
echo "Esperando que el servicio esté listo..."
for i in {1..30}; do
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        echo "✓ Servicio listo"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Timeout esperando el servicio"
        echo ""
        echo "Logs del contenedor:"
        sudo docker logs gestion-documental
        exit 1
    fi
    echo "  Intento $i/30..."
    sleep 1
done

echo ""
echo "========================================="
echo "¡Deployment completado!"
echo "========================================="
echo ""
IP=$(hostname -I | awk '{print $1}')
echo "URL: http://$IP:8000"
echo ""
echo "Comandos útiles:"
echo "  Ver logs:           sudo docker logs -f gestion-documental"
echo "  Reiniciar:          sudo docker restart gestion-documental"
echo "  Ver estado:         sudo docker ps | grep gestion-documental"
echo ""
