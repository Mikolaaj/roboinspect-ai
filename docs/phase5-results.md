# Odbiór fazy 5a — 18.10.2026

Wdrożono rdzeń API i misji opisany w [missions.md](missions.md).

- Ruff check i format: poprawne.
- Pytest: 21 testów zaliczonych. Jedno ostrzeżenie zależności Starlette o
  przyszłym przejściu TestClient z httpx na httpx2; brak błędów testów.
- Rzeczywisty Gazebo/Nav2: trzy zmieniające się obrazy, odrzucenie drugiego
  celu, anulowanie podczas ruchu i potwierdzone zatrzymanie.
- Przejazdy pojedyncze: A i BASE zakończone sukcesem; błąd względem pozycji
  świata Gazebo: odpowiednio 0.063 m i 0.373 m.
- Jedna misja A → BASE: oba kroki wykonane kolejno. Powtórzone żądanie
  zwróciło ten sam identyfikator, a inna aktywna misja została odrzucona.
- Anulowana sekwencja A → B → BASE: A anulowane podczas ruchu,
  B i BASE pominięte; prędkość liniowa i kątowa po anulowaniu zerowe.
- Zatrzymanie i ponowny start kokpitu: poprzednia misja nadal `succeeded`,
  anulowana nadal `canceled`, robot gotowy, bez aktywnego przejazdu.
- Akceleracja: renderer NVIDIA RTX 4060 Laptop, rzeczywisty proces Gazebo
  na GPU (50 MiB); FPV 10.39, follow 4.59, overhead 3.79 kl./s w próbce.
  Fizyka, ROS i wykonawca pozostają na CPU.

Raporty: [nawigacja](verification/phase5-navigation.json),
[misje i zdarzenia](verification/phase5-missions.json),
[restart](verification/phase5-restart.json), [GPU](verification/phase5-gpu.json).

Restart aktywnej misji, utratę potwierdzenia wysłania i zakaz ponawiania
ruchu sprawdzono w testach wykonawcy z adapterem testowym. Test rzeczywistego
restartu dotyczył zapisanych, zakończonych misji. Nie symulowano awarii
sprzętowej. Testy nie stanowią certyfikacji bezpieczeństwa robota fizycznego.

Workflow CI zapisano w repo; nie był jeszcze uruchamiany na GitHub.
PostgreSQL, Pydantic Graph, tracing, LLM i percepcja pozostają w planie.
