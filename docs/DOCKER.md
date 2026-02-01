# Optimasol Docker usage (app + Mosquitto in one container)

## Build
```bash
docker build -t optimasol .
```

## Run modes
- **Service 24/7 (main loop + MQTT broker)**  
  ```bash
  docker run -d --name optimasol \
    -p 8000:8000 -p 1883:1883 \
    -v optimasol-data:/opt/optimasol/data \
    -v optimasol-backups:/opt/optimasol/backups \
    optimasol service
  ```
- **API/GUI**  
  ```bash
  docker run -d --name optimasol-api \
    -p 8000:8000 -p 1883:1883 \
    -v optimasol-data:/opt/optimasol/data \
    -v optimasol-backups:/opt/optimasol/backups \
    optimasol api
  ```
- **CLI ponctuelle**  
  ```bash
  docker run --rm \
    -v optimasol-data:/opt/optimasol/data \
    -v optimasol-backups:/opt/optimasol/backups \
    optimasol cli status
  ```

## Notes
- Mosquitto tourne dans le même conteneur (listener 1883, anonymes autorisés). L’app peut utiliser `host=localhost`, `port=1883`.
- Données persistantes : volumes `optimasol-data` (BDD SQLite, logs) et `optimasol-backups`.
- Compatible ARM/AMD64 (base `python:3.11-slim`). Pour Raspberry Pi : `docker build --platform linux/arm64 -t optimasol .`

## docker-compose (optionnel)
Un lancement encore plus simple :
```yaml
version: "3.8"
services:
  optimasol:
    image: optimasol:latest
    build: .
    command: service
    ports:
      - "8000:8000"
      - "1883:1883"
    volumes:
      - optimasol-data:/opt/optimasol/data
      - optimasol-backups:/opt/optimasol/backups
    restart: unless-stopped
volumes:
  optimasol-data:
  optimasol-backups:
```
Lancement : `docker compose up -d`
