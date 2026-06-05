#!/bin/bash

# Script para verificar que la compilación Docker funcionará correctamente
# Uso: ./verify-build.sh

set -e

echo "========================================="
echo "Verificando requisitos..."
echo "========================================="

# Verificar archivos necesarios
REQUIRED_FILES=(
    "modelo/modelo_resnet50.keras"
    "modelo/config.json"
    "index.html"
    "app.py"
    "consulta_modelo.py"
    "requirements.txt"
    "Dockerfile"
    ".dockerignore"
)

MISSING=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Falta: $file"
        MISSING=$((MISSING + 1))
    else
        size=$(du -h "$file" | cut -f1)
        echo "✓ $file ($size)"
    fi
done

if [ $MISSING -gt 0 ]; then
    echo ""
    echo "❌ Faltan $MISSING archivos necesarios"
    exit 1
fi

echo ""
echo "========================================="
echo "Verificando tamaños..."
echo "========================================="

MODELO_SIZE=$(du -sh modelo/modelo_resnet50.keras | cut -f1)
echo "Modelo: $MODELO_SIZE"

if [ ! -f "modelo/modelo_resnet50.keras" ] || [ ! -s "modelo/modelo_resnet50.keras" ]; then
    echo "❌ El archivo del modelo está vacío o no existe"
    exit 1
fi

echo ""
echo "========================================="
echo "Verificando config.json..."
echo "========================================="

if ! python3 -c "import json; json.load(open('modelo/config.json'))" 2>/dev/null; then
    echo "❌ config.json es inválido"
    cat modelo/config.json
    exit 1
fi

CLASSES=$(python3 -c "import json; c = json.load(open('modelo/config.json')); print(len(c.get('clases', [])))")
IMG_SIZE=$(python3 -c "import json; c = json.load(open('modelo/config.json')); print(c.get('img_size', []))")

echo "✓ Clases: $CLASSES"
echo "✓ Tamaño imagen: $IMG_SIZE"

echo ""
echo "========================================="
echo "Verificando Python..."
echo "========================================="

if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version)
    echo "✓ $PY_VERSION"
else
    echo "❌ Python 3 no encontrado"
    exit 1
fi

# Verificar requisitos instalados localmente (opcional)
if [ -f ".venv/bin/python" ]; then
    echo "✓ .venv existe"

    if .venv/bin/python -c "import tensorflow" 2>/dev/null; then
        TF_VERSION=$(.venv/bin/python -c "import tensorflow; print(tensorflow.__version__)")
        echo "✓ TensorFlow $TF_VERSION en .venv"
    fi
fi

echo ""
echo "========================================="
echo "Verificando Git..."
echo "========================================="

if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    COMMITS=$(git rev-list --count $BRANCH)
    echo "✓ Git repo en rama: $BRANCH ($COMMITS commits)"

    # Verificar que .git ignora lo necesario
    if git check-ignore -q CLAUDE.md; then
        echo "✓ CLAUDE.md en .gitignore"
    else
        echo "⚠ CLAUDE.md NO está en .gitignore (debería estarlo)"
    fi

    if git check-ignore -q .venv; then
        echo "✓ .venv en .gitignore"
    else
        echo "❌ .venv NO está en .gitignore"
        exit 1
    fi
else
    echo "❌ No es un repositorio Git"
    exit 1
fi

echo ""
echo "========================================="
echo "Listo para Docker!"
echo "========================================="
echo ""
echo "Próximos pasos:"
echo "  1. git add ."
echo "  2. git commit -m 'Ready for AWS deployment'"
echo "  3. git push origin main"
echo "  4. En AWS: curl -sSL https://raw.githubusercontent.com/pintoMACRO/GestionDocumental/main/deploy-aws.sh | bash"
echo ""
