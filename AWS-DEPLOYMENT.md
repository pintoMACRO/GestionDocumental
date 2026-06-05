# Deployment en AWS

## Quick Start

```bash
# En tu máquina local
git push origin main

# En la instancia EC2
curl -sSL https://raw.githubusercontent.com/pintoMACRO/GestionDocumental/main/deploy-aws.sh | bash

# Luego (después de logout/login para docker)
newgrp docker
```

## Requisitos de la Instancia EC2

- **Tipo**: t3.medium o superior (t3.micro/small pueden quedarse sin RAM)
- **Disco**: 20+ GB (modelo es ~250MB, pero necesita espacio de trabajo)
- **RAM**: Mínimo 2GB para que TensorFlow tenga espacio
- **Ubuntu**: 22.04 LTS o 20.04 LTS (las probadas)

## Troubleshooting

### El contenedor se inicia pero muere rápidamente

```bash
docker logs gestion-documental
```

**Problema**: "No space left on device"
- Libera espacio: `docker system prune -a`
- O agrega más disco a la instancia

**Problema**: "Out of memory"
- El modelo necesita ~1.5-2GB de RAM
- Escala a t3.medium o superior
- Verifica: `free -h` (debe haber >1GB disponible)

**Problema**: "cannot import tensorflow" o "module not found"
- El Dockerfile instala las dependencias, pero puede fallar por network
- Reinicia el build: `docker build --no-cache -t gestion-documental:latest .`

### El servicio no responde en http://[IP]:8000

1. Verifica que el contenedor está corriendo:
   ```bash
   docker ps
   ```
   Si no aparece, revisa los logs:
   ```bash
   docker logs gestion-documental
   ```

2. Verifica que el puerto está abierto en AWS Security Group:
   - Inbound Rules → Agregar: TCP 8000 desde 0.0.0.0/0

3. Verifica que puedes conectar localmente:
   ```bash
   curl http://localhost:8000/
   ```

4. Si ves HTML pero no funciona, verifica los logs:
   ```bash
   docker logs -f gestion-documental
   ```

### El modelo no se encuentra

El Dockerfile verifica que `modelo/modelo_resnet50.keras` existe. Si falla:

```bash
ls -lh modelo/
```

Si está vacío o falta:
1. En local: `git add modelo/` y `git push`
2. En la instancia: `git pull origin main`
3. Rebuild: `docker build -t gestion-documental:latest .`

### Actualizaciones del código

```bash
cd GestionDocumental
git pull origin main
docker build -t gestion-documental:latest .
docker restart gestion-documental
```

O si solo cambiaron archivos estáticos (HTML):
```bash
git pull origin main
docker restart gestion-documental
```

### Ver logs en tiempo real

```bash
docker logs -f gestion-documental
```

Cada inferencia imprime `[predict] ...`, así puedes ver en vivo qué está pasando.

## Memory & Performance

### Memoria disponible

- **Modelo**: ~250MB on disk, ~500MB loaded in RAM
- **TensorFlow + Dependencies**: ~300-400MB
- **Inference buffer**: ~200-500MB dependiendo del tamaño de imagen
- **Total recomendado**: 2GB de RAM libre

Verifica:
```bash
free -h
docker stats gestion-documental
```

### CPU

El modelo usa CPU para inferencia. Si las predicciones son lentas:
- Verifica CPU: `docker stats` (% CPU)
- Aumenta instance type (t3.medium, t3.large)
- O reduce `OMP_NUM_THREADS` en el Dockerfile (ya está en 1)

## Monitoreo Básico

```bash
# Health check manual
curl -w "\n%{http_code}\n" http://localhost:8000/

# Stats del contenedor
docker stats gestion-documental --no-stream

# Logs de errores
docker logs gestion-documental | grep -i error

# Reiniciar si se cuelga
docker restart gestion-documental
```

## Production Hardening (Opcional)

Para producción real, considera:

1. **Reverse Proxy (Nginx)**
   ```bash
   sudo apt install nginx
   # Configurar proxy_pass a http://localhost:8000
   ```

2. **HTTPS (Certbot + Let's Encrypt)**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot certonly --nginx -d tu-dominio.com
   ```

3. **Limitar CORS**
   - En `app.py:281`: cambiar `allow_origins=["*"]` a tu dominio

4. **Rate Limiting**
   - Agregar middleware en Starlette para evitar abuse

5. **Logs a CloudWatch**
   ```bash
   docker run -d \
     --log-driver awslogs \
     --log-opt awslogs-group=/aws/ecs/gestion-documental \
     ...
   ```

## Debugging Network

Si no puedes conectar:

```bash
# ¿Escucha en el puerto?
sudo netstat -tlnp | grep 8000

# ¿El contenedor tiene IP?
docker inspect gestion-documental | grep IPAddress

# ¿Puedes hacer ping a la instancia?
ping [EC2-IP]

# ¿El Security Group permite 8000?
# Ve a AWS Console → EC2 → Instances → Tu instancia → Security
```

## Migrar a Otro Tipo de Instancia

Si necesitas cambiar el tamaño:

```bash
# Detener instancia
docker stop gestion-documental
docker rm gestion-documental

# En AWS: Stop → Change Instance Type → Start

# Reiniciar aplicación
docker run -d --restart unless-stopped -p 8000:8000 --name gestion-documental gestion-documental:latest
```

## Backup del Modelo

Si entrenas nuevos modelos:

```bash
# Local: guardar y versionar
git add modelo/
git commit -m "Update ResNet50 model and classes"
git push origin main

# AWS: actualizar
cd GestionDocumental
git pull origin main
docker build -t gestion-documental:latest .
docker restart gestion-documental
```
