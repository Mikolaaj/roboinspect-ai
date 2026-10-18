# Wyniki: Whisper i czerwone strefy

Sprawdzenie lokalne 18.10.2026, RTX 4060 Laptop 8 GB, ROS Jazzy i Gazebo Harmonic.

- 86 testów Python oraz 5 testów sterowania nagrywaniem w JavaScript przeszło. Testy obejmują limity audio, ciszę, uszkodzony plik, integralność modelu, Host/Origin, niezależny STOP, anulowanie i spóźnione wyniki.
- Prawdziwy lokalny Whisper rozpoznał syntetyczną polską wypowiedź WAV: „Jedź do sektora A. Jedź do bazy.”, 2.61 s nagrania, 2.49 s transkrypcji CPU INT8, wraz z pierwszym ładowaniem modelu. Czas nie obejmuje zapisu metryk MLflow. WebM/Opus: „Jedź do sektora A. I wróć do bazy.”, 1.28 s transkrypcji na załadowanym modelu.
- Metryki obu transkrypcji zapisano w eksperymencie roboinspect-whisper. Surowego audio nie zapisuje usługa; pliki w artifacts/speech-check są wyłącznie dźwiękiem syntetycznym testu.
- Samo rozpoznanie nie tworzy misji. Po wysłaniu rozpoznanej komendy do Bielika powstała misja A, BASE, Nav2 rozpoczęło ruch, tekstowy STOP zatrzymał zadanie w około 0.97 s i osobny przejazd zakończył się w BASE.
- Nav2 wykonało przejazd A, B, C, BASE. Błędy rzeczywistej pozycji Gazebo: A 0.084 m, B 0.031 m, C 0.076 m, BASE 0.131 m. Wszystkie cele zakończyły się sukcesem. Sprawdzono również anulowanie w ruchu i brak dryfu po zatrzymaniu.
- Wszystkie trzy kamery dostarczały obraz. Czerwone znaczniki są widoczne z góry i jako nakładka na mapie. Generator potwierdza po jednej strefie na sektor, brak kolizji znaczników, osiągalność nowych celów i zachowanie niedostępnego B w scenariuszu negatywnym.
- Panel telefonu 390 px nie przewija się w poziomie, mikrofon jest dostępny, przejście do czatu ustawia jego górę pod mobilnym paskiem.

Nie nagrywano sprzętowego mikrofonu użytkownika. Jego zgodę przeglądarki i jakość naturalnej mowy trzeba sprawdzić na urządzeniu według [instrukcji](voice-and-inspection-zones.md). Wstępne próby syntetyczne bez słownika sektorów zawierały błędy; dodano kontekst nazw i zachowano obowiązkowe sprawdzenie tekstu przed wysłaniem. Te próbki nie stanowią pomiaru WER dla polskiej mowy.

Raporty: [WAV](verification/whisper.json), [WebM](verification/whisper-webm.json), [przepływ do Nav2](verification/whisper-bielik-navigation.json), [przejazdy](verification/inspection-zones.json), [UI](verification/voice-ui.json).
