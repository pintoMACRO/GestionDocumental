# GestionDocumental

## Docker

Construcción local:

```bash
docker build -t gestion-documental:latest .
docker run --rm -p 8000:8000 gestion-documental:latest
```

En la VM Ubuntu:

```bash
git pull origin main
docker build -t gestion-documental:latest .
docker run -d --restart unless-stopped -p 8000:8000 --name gestion-documental gestion-documental:latest
```

Puerto a habilitar en AWS: `8000/TCP`.