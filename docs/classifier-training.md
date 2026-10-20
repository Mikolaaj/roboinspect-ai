# Pierwszy trening klasyfikatora stanu tablicy

Wdrożony pipeline obejmuje przegląd i zamrożenie danych, prosty model porównawczy, dostrojenie ResNet18, wybór modelu na walidacji, końcową ocenę testową, zapis modeli i MLflow. Model nie jest jeszcze używany przez wykonawcę inspekcji robota.

## Jak zobaczyć wynik

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_cockpit.sh
```

W panelu sterowania rozwiń **Dane do modelu usterek**, następnie wybierz **Wyniki treningu klasyfikatora**. Strona `/classifier` pokazuje porównanie accuracy i macro F1, metryki klas, macierze pomyłek, snapshot danych i ograniczenia. Przycisk MLflow prowadzi do lokalnego serwera; wybierz eksperyment **roboinspect-classifier**, uruchomienie nadrzędne `pilot-classifier-...`, a następnie potomne `baseline` i `resnet18`.

Zatrzymanie wszystkich usług kokpitu:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
```

## Dane i przegląd

Zbiór ma 200 obserwacji: 120 treningowych, 40 walidacyjnych i 40 testowych. Wszystkie części zawierają pięć klas: `clean`, `cracked`, `dirty`, `occluded`, `missing`. Źródła są grupowane po SHA256 oryginalnego zdjęcia, także dla sąsiednich tablic w klatce. Grupy źródłowe: 14 treningowych, 5 walidacyjnych i 5 testowych. Odrębne warianty jednego zdjęcia nie przechodzą między częściami.

Wcześniejsze 34 zatwierdzenia (w większości zbiorcze na polecenie użytkownika) pozostają w historii. Przed tym treningiem asystent przejrzał wizualnie 166 nowych wycinków na 11 arkuszach i zatwierdził ich czytelność oraz zgodność z pięcioma syntetycznymi stanami. Ślad jest w `review_history` oraz `artifacts/training-review/`. To przegląd pilotażowy, nie niezależna ekspercka anotacja rzeczywistych defektów.

`freeze_dataset` bierze wyłącznie rekordy `approved` z `training_ready=true`. Weryfikuje pliki, sumy kontrolne, pochodzenie źródeł, obecność klas w każdej części i przecieki. Kopiuje wycinki do `data/classifier/snapshots/<SHA256>/images` i zapisuje manifest obejmujący etykiety, historię, źródła i preprocessing. Późniejsze zmiany w panelu nie zmieniają istniejącego snapshotu. Uszkodzenie manifestu lub obrazu snapshotu przerywa trening.

## Algorytmy i wybór

- Baseline: 106 cech obrazu (histogramy RGB, statystyki koloru, jasności i krawędzi w siatce), standaryzacja dopasowana wyłącznie na treningu, wieloklasowa regresja ridge. Parametr regularizacji wybierany spośród 0.1, 1 i 10 na walidacji.
- CNN: ResNet18 z oficjalnymi wagami ImageNet `resnet18-f37072fd.pth`. Dostrajany jest ostatni blok (`layer4`) i nowa głowica pięciu klas. Wcześniejsze wagi i statystyki BatchNorm pozostają zamrożone. AdamW, learning rate 0.0001/0.001, weight decay 0.001, batch 16, limit 25 epok, early stopping po 6 epokach bez poprawy.
- Preprocessing obu ścieżek: pełna tablica dopasowana do 224×224 z szarym dopełnieniem. Nie stosujemy centralnego kadrowania mogącego usunąć defekt. CNN używa normalizacji ImageNet. Augmentacje treningowe: odbicie poziome, obrót do 3 stopni i jasność 0.9–1.1. Brak augmentacji walidacji/testu.
- Wybór najlepszej epoki i modelu: macro F1 walidacji, następnie accuracy; remis modeli rozstrzyga prostszy baseline. `selection.json` jest zapisany przed pierwszą predykcją testową. Test służy końcowej ocenie, nie zmianie konfiguracji.

Źródła implementacji transfer learning: [oficjalny tutorial PyTorch](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial) i [definicja wag ResNet18 w Torchvision](https://docs.pytorch.org/vision/main/_modules/torchvision/models/resnet.html). SHA256 pobranych wag, wersje bibliotek, seed, hashe kodu i wersja danych są zapisane w eksperymencie. Kod używa już istniejącego środowiska wizji, bez instalowania drugiego stosu PyTorch.

## Ponowny trening

Wymagane istniejące środowisko aplikacji i wizji, przygotowane przez `scripts/setup_project.sh` oraz `scripts/setup_vision.sh`. Środowisko wizji ma PyTorch 2.7.1+cu128 i Torchvision 0.22.1. MLflow działa z głównego `.venv`; worker GPU korzysta z `data/vision/env`. ROS i Gazebo nie muszą działać.

```bash
cd ~/Desktop/roboinspect-ai
.venv/bin/python scripts/train_classifier.py --epochs 25 --seed 42
```

Na nowym komputerze oficjalne wagi są pobierane z `download.pytorch.org`; istniejący lokalny cache jest używany w pierwszej kolejności. Wagi muszą mieć przypięty prefiks SHA256 `f37072fd`, pełny hash jest rejestrowany. Trening wymaga CUDA; brak GPU kończy ten profil błędem, nie uruchamia ukrytego wolnego treningu CPU.

Polecenie tworzy nowy run i może zastąpić wskaźnik `data/classifier/latest.json`, ale zachowuje wcześniejsze runy i snapshoty. Nie należy powtarzać eksperymentów po obejrzeniu wyników testowych w celu poprawiania tych samych wyników. Przy zmianach modelu do niezależnej oceny potrzebny jest nowy, nietknięty zestaw testowy. Identyczny seed ogranicza losowość, jednak nie gwarantuje identycznych wag na każdym sprzęcie i wersji bibliotek.

## Sprawdzenie zapisanego modelu

Używaj wycinka tablicy, nie całego widoku hangaru. Przykład na istniejącej próbce:

```bash
cd ~/Desktop/roboinspect-ai
.venv/bin/python scripts/predict_classifier.py \
  --image data/dataset/samples/aca60d95-21b7-43b7-b100-ebd49f78cd1c/crop.jpg
```

Oczekiwany stan: `cracked`. Możesz wskazać własny wycinek. Opcjonalne `--model baseline` lub `--model resnet18` wybiera konkretny model. Domyślne `selected` odczytuje wybór z walidacji. Polecenie sprawdza hash modelu oraz zgodność klas, preprocessingu i snapshotu. Nie pobiera nowych wag i nie uruchamia misji. Wynik `scores` jest nieskalibrowanym softmaxem, nie gwarancją poprawności i nie prawdopodobieństwem awarii urządzenia.

## Wyniki pierwszego uruchomienia

| Model | Walidacja accuracy | Walidacja macro F1 | Test accuracy | Test macro F1 |
|---|---:|---:|---:|---:|
| Cechy + ridge | 0.650 | 0.628 | 0.650 | 0.664 |
| ResNet18, epoka 8 | 0.975 | 0.975 | 1.000 | 1.000 |

ResNet18 trafił 40 z 40 kadrów testowych, baseline 26 z 40. Nie oznacza to 100% jakości na rzeczywistych awariach. Test ma tylko 40 skorelowanych kadrów pochodzących z 5 fotografii; usterki są prostymi generowanymi efektami. Obserwacje mają w większości kontrolowane pozycje i stałe oświetlenie. Połączenie inspekcji Nav2 z kadrami nieruchomego podwozia może również wpływać na wyniki. Nie wykonywano kalibracji, badań OOD ani niezależnej anotacji. Model pozostaje pilotażowy.

Snapshot: `87023d75944ca02077e6341d6012ceb90a03cea18d20585d0795e40cdd98680f`. Wyniki do repo: `docs/verification/classifier-training.json`. Modele, zdjęcia, snapshoty i pełne wyniki pozostają w ignorowanym `data/`. MLflow zapisuje metryki klas, macierze, przebieg uczenia, modele, hashe, manifest i kod użyty w eksperymencie. Eksperyment nie rejestruje automatycznie modelu jako produkcyjnego.

Następne prace: integracja klasyfikatora z inspekcją, nowy zbiór oceny obejmujący inne zdjęcia i warunki, kalibracja i ewentualne strojenie Optuna wyłącznie na treningu/walidacji.
