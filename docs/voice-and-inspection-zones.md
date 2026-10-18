# Mikrofon, lokalny Whisper i strefy inspekcji

## Uruchomienie

Zatrzymaj poprzednią sesję i poczekaj na potwierdzenie:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
```

Na tym komputerze silnik i model są już zainstalowane. Po sklonowaniu repo na nowym komputerze wykonaj jednorazowo:

```bash
bash scripts/setup_project.sh
bash scripts/setup_bielik.sh
bash scripts/setup_whisper.sh
```

Potem jedna komenda uruchamia cały stos i otwiera dwie karty:

```bash
bash scripts/run_cockpit.sh
```

Model ASR nie wymaga oddzielnej usługi ani terminala. Pierwsze nagranie ładuje model do pamięci. Kolejne korzystają z załadowanej instancji.

## Jak używać mikrofonu

1. Otwórz panel sterowania, poczekaj na gotowość Nav2 i przycisk Mikrofon.
2. Kliknij Mikrofon i zezwól przeglądarce na użycie urządzenia.
3. Powiedz np. „Jedź do sektora B i wróć do bazy”.
4. Kliknij Zakończ nagranie. Nagranie kończy się również automatycznie przed limitem 30 sekund.
5. Sprawdź tekst w polu wiadomości, popraw ewentualne pomyłki i naciśnij Enter lub Wyślij.
6. Obserwuj przejazd oraz historię. Samo rozpoznanie tekstu nie uruchamia misji.

Anuluj nagranie zwalnia mikrofon i odrzuca nagranie. Podczas rozpoznawania przycisk Anuluj rozpoznawanie odrzuca oczekiwany wynik. Obliczenia już uruchomione w Whisperze mogą dokończyć się w tle, ale nie utworzą misji. Zamknięcie lub ukrycie nagrywającej karty również zwalnia mikrofon.

Wpisany tekst nie jest nadpisywany przez spóźnioną transkrypcję. Wysłanie wiadomości, także STOP, unieważnia trwające nagranie lub rozpoznawanie. Do szybkiego zatrzymania robota użyj Anuluj przejazd albo tekstowego STOP. Głos wymaga rozpoznania i nie jest awaryjnym przyciskiem bezpieczeństwa.

Nagrywanie działa na localhost i HTTPS, zależy od zgody przeglądarki i dostępnego mikrofonu. Otwarcie panelu po HTTP przez adres IP innego komputera może uniemożliwić nagrywanie. W przypadku braku zgody można nadal używać klawiatury.

## Model i zasoby

Używamy faster-whisper 1.2.1 oraz wielojęzycznego Whisper small, repozytorium Systran/faster-whisper-small, rewizja `536b0662742c02347bc0e980a01041f333bce120`. Jest to model w formacie CTranslate2, nie model trenowany w tym projekcie. Pliki zajmują około 464 MiB. Zapis konfiguracji: [speech.json](../config/speech.json).

Ustawienia domyślne: język polski, CPU, INT8, 4 wątki, jedna transkrypcja naraz. RTX pozostaje do renderowania i Bielika. Słownik kontekstu obejmuje nazwy sektorów i punktów; nie zastępuje rozpoznawania ani walidacji. Mowa niewyraźna i syntetyczna może zostać rozpoznana błędnie, zwłaszcza pojedyncze litery. Wymagana jest kontrola transkrypcji przez operatora.

Model pobierany jest tylko przez skrypt instalacji. Runtime używa wyłącznie lokalnych plików i weryfikuje manifest SHA256 przed pierwszym załadowaniem. Nagrania mają limit 2 MiB i 30 sekund, dekoder odrzuca zbyt długi dźwięk także wtedy, gdy metadane kontenera są nieprawidłowe. Nie zapisujemy nagrań na dysku i nie wysyłamy ich do usług rozpoznawania w chmurze. Tekst wysłany przez operatora trafia do dotychczasowej lokalnej historii czatu i eksperymentu Bielika.

MLflow: eksperyment `roboinspect-whisper`, widok Model training / Runs. Dla udanych transkrypcji zapisujemy wersję modelu, urządzenie, liczbę wątków, hash słownika, czas nagrania, czas rozpoznawania i współczynnik czasu rzeczywistego. Eksperyment nie zawiera surowego nagrania ani treści transkrypcji. Błąd MLflow jest sygnalizowany, ale nie usuwa poprawnie rozpoznanego tekstu.

Źródła: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [model](https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120). Licencje modelu i silnika znajdują się w ich repozytoriach; model README pobierany jest razem z wagami.

## Czerwone strefy

| Sektor | Tablice | Cel w świecie, metry | Ustawienie robota |
|---|---|---|---|
| A | P1 i P2 | x = -9, y = 5 | w stronę tablic, yaw = pi/2 |
| B | P3 i P4 | x = 1, y = 5 | w stronę tablic, yaw = pi/2 |
| C | P5 | x = 10, y = 6.6 | w stronę tablic, yaw = pi/2 |

Każdy sektor ma jedną czerwoną strefę namalowaną na podłodze. A i B mają wymiary 2 × 1.4 m, C 1.6 × 1.4 m. Przyciski A/B/C i misje tekstowe prowadzą do środka tych stref. Precyzyjne cele P1 do P5 pozostają dostępne osobno. Dawne małe żółte znaczniki P usunięto z wizualizacji.

Znaczniki nie mają kolizji, więc nie tworzą przeszkód dla lidarów ani SLAM. Czerwone prostokąty w panelu są nakładką na mapę; nie zmieniają mapy zajętości. Nakładka uwzględnia zarówno współrzędne SLAM, jak i mapę nawigacyjną.

Pole widzenia kamery robota wynosi 1.5 radiana, aby z jednej wspólnej strefy mieściła się para tablic. Nav2 zachowuje tolerancję dojazdu 0.1 m i orientacji 0.15 radiana. Scenariusz niedostępnego B przeniesiono do nowej pozycji B. Geometria normalnego hangaru nie zmieniła przeszkód, więc dotychczasowa mapa SLAM nadal nadaje się do nawigacji.

## Weryfikacja

Testy programu i sterowania nagrywaniem, Node.js 18+ oraz Python:

```bash
bash scripts/test_project.sh -q
```

Po uruchomieniu kokpitu test rzeczywistego Whispera z syntetycznym polskim nagraniem, bez dostępu do mikrofonu użytkownika:

```bash
.venv/bin/python scripts/check_speech.py
```

Wymaga systemowej biblioteki libespeak-ng1. Możesz też użyć krótkiego pliku WAV przez `--audio /pełna/ścieżka/nagranie.wav`. Test potwierdza, że transkrypcja sama nie tworzy misji. Uruchamiaj go przy nieruchomym robocie.

Rzeczywisty przejazd przez wszystkie nowe strefy:

```bash
.venv/bin/python scripts/check_cockpit.py --existing --goals A B C BASE --output-dir artifacts/inspection-zones-check
```

To uruchamia ruch w symulacji i test anulowania. Weryfikuje dojazd na podstawie rzeczywistej pozycji Gazebo. Test syntetyczny nie potwierdza jakości konkretnego mikrofonu ani rozpoznania każdej ludzkiej wypowiedzi.
