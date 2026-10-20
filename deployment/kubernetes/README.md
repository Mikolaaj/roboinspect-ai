# Manifesty Kubernetes

Źródłem konfiguracji jest `scripts/render_kubernetes.py`. Ten sam renderer jest używany przez uruchomienie aplikacji i test integracyjny, aby nie utrzymywać dwóch rozbieżnych kopii YAML.

Przykład renderowania pliku do przejrzenia:

```bash
.venv/bin/python scripts/render_kubernetes.py \
  --gateway-image ghcr.io/mikolaaj/roboinspect-ai-gateway:sha-PELNY_SHA \
  --mlflow-image ghcr.io/mikolaaj/roboinspect-ai-mlflow:sha-PELNY_SHA \
  --upstream http://ADRES_BRAMY_DOCKER:18767 > /tmp/roboinspect-manifest.json
```

Do uruchamiania użyj `bash scripts/run_kubernetes.sh`, które przygotowuje także kind, most, Secret, lokalnego operatora i przekazywanie portów. Samo apply manifestu nie uruchamia lokalnego ROS i mostu. Szczegóły: `docs/kubernetes.md`.
