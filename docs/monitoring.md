# Monitoring usług

Prometheus: http://127.0.0.1:9090, także przycisk Monitoring w panelu. W Compose jest uruchamiany razem z kokpitem; w Kubernetes jako oddzielny Deployment i Service.

Zacznij od Status > Targets. Target `roboinspect-gateway` powinien mieć stan UP. W zakładce zapytań sprawdź:

| Zapytanie | Znaczenie |
| --- | --- |
| `roboinspect_executor_ready` | 1, gdy lokalny wykonawca odpowiada jako zdrowy; 0 przy braku gotowości |
| `rate(roboinspect_http_requests_total[5m])` | Żądania na sekundę |
| `rate(roboinspect_http_errors_total[5m])` | Odpowiedzi 5xx lub wyjątki na sekundę |
| `rate(roboinspect_http_headers_seconds_total[5m]) / clamp_min(rate(roboinspect_http_requests_total[5m]), 0.0001)` | Średni czas do odpowiedzi z nagłówkami |

Czas odpowiedzi obejmuje nagłówki, nie pełną długość strumienia kamery. Licznik aktywnych żądań również kończy pomiar na nagłówkach. Nie jest to liczba otwartych strumieni. Liczniki resetują się po restarcie bramy. Endpointy health i sam odczyt metrics nie zwiększają liczników.

Reguły alertów wykrywają brak bramy, brak wykonawcy i wzrost błędów. Są widoczne w Prometheus Alerts. Nie ma Alertmanagera ani wysyłania powiadomień. To monitoring usług HTTP, nie pomiar użycia GPU i CPU ani ocena jakości detekcji. Jakość, parametry i wyniki modeli pozostają w MLflow.

Metryki nie zawierają treści czatu, tokenów, etykiet użytkownika ani dowolnych ścieżek URL. Most do ROS wymaga tokenu także przy odczycie health i metrics.

Compose przechowuje metryki w nazwanym wolumenie z retencją 7 dni. Kubernetes używa tymczasowego emptyDir; dane Prometheusa znikają po odtworzeniu jego poda. Baza i artefakty MLflow są trwałe w obu trybach.

Weryfikacja: `promtool check config` potwierdził poprawność konfiguracji Compose oraz trzech reguł. W teście Kubernetes Prometheus odczytał `roboinspect_executor_ready=1` z rzeczywistej bramy. Metryki sprawdzono także podczas przejazdu symulowanego robota.
