# Lokalny RAG operatora

RAG jest osobnym torem odpowiedzi o obsłudze. Nie uruchamia nawigacji ani mapowania. STOP omija zarówno wyszukiwanie, jak i Bielika. Pytania o to, co robot widział w sektorze, nadal korzystają z zapisanych inspekcji w bazie, a nie z instrukcji.

## Przygotowanie i uruchomienie

Na tym komputerze model i indeks są już przygotowane. Na nowym klonie, po instalacji zależności i Bielika:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/setup_rag.sh
```

Skrypt pobiera EmbeddingGemma 300M z oficjalnego rejestru Ollama, sprawdza SHA256 wag i buduje indeks. Pobranie to około 622 MB. Po tym kroku pytania i wektory pozostają lokalne; działanie nie wymaga Internetu.

Zatrzymanie całego projektu:

```bash
bash scripts/stop_cockpit.sh
```

Poczekaj na potwierdzenie zamknięcia. Ponowny start kokpitu i sterowania:

```bash
bash scripts/run_cockpit.sh
```

Osobny proces embeddingów uruchamia się i zamyka wraz z kokpitem. Działa na CPU pod adresem pętli zwrotnej 11436, niezależnie od Bielika na 11435. Zapytania wymuszają `num_gpu=0`. Nie wypiera modelu Bielika z pamięci RTX. Log: `artifacts/cockpit/rag-embeddings.log`.

## Sprawdzenie w panelu

Odśwież panel przez Ctrl+Shift+R. Zapytaj kolejno:

- Jak rozpocząć mapowanie?
- Co oznacza żółta linia?
- Co oznacza procent przy detekcji?
- Gdzie znajdę wyniki MLflow?
- Jaka jutro pogoda w Warszawie?

Przy odpowiedziach z instrukcji pojawia się rozwijane „Źródła instrukcji”. Zawiera tytuł, wykorzystany fragment i link do publicznej instrukcji. Pytanie spoza bazy powinno otrzymać informację o braku wiedzy. Żadne z tych pytań nie zleca ruchu. „Co robot widział w sektorze A?” odczytuje obserwacje; „Jedź do A” jest odrębnym poleceniem nawigacyjnym.

## Dokumenty, indeks i modele

Źródłem są wyłącznie jawnie utrzymywane dokumenty `knowledge/operator/*.md`. Nie indeksujemy repozytorium, konfiguracji, sekretów, logów, historii rozmowy ani Internetu. Dowiązania symboliczne są odrzucane. Instrukcja jest też dostępna w `/guide`. Odpowiedzi nie mają dostępu do narzędzi wykonawczych, a tekst źródeł w interfejsie jest renderowany jako tekst, nie HTML.

Dokumenty są dzielone na fragmenty do około 1000 znaków przy granicach zdań. Liczba fragmentów zależy od bieżącej wersji instrukcji i jest podawana podczas przygotowania indeksu. EmbeddingGemma tworzy 768-wymiarowe wektory. Indeks to lokalna macierz NumPy zapisana w `data/rag/index.json`; przy tej wielkości zbioru nie potrzebujemy osobnej bazy wektorowej. Zmiana treści unieważnia indeks według SHA256 i powoduje przebudowę przy kolejnym pytaniu.

Wyszukiwanie: podobieństwo kosinusowe, następnie lekkie dopasowanie słów dla nazw przycisków i polskich terminów. Maksymalnie 3 fragmenty, minimalny wynik semantyczny 0.28 i odległość od najlepszego wyniku do 0.12 po dopasowaniu słów. Wynik wyszukiwania nie jest prawdopodobieństwem poprawności odpowiedzi. Osobna kontrola zakresu odrzuca pytania bez terminów związanych z obsługą.

Bielik otrzymuje pytanie i znalezione fragmenty, zwraca odpowiedź strukturalną z identyfikatorami źródeł. Aplikacja odrzuca nieznane cytowania i odpowiedzi naruszające zakres operatora. Dodatkowy test wykrywa zaobserwowaną pomyłkę polegającą na umieszczaniu żółtej trasy na mapie SLAM zamiast osobnego planu 2D. Model może zgłosić brak wiedzy mimo podobnych fragmentów. Przy błędzie generowania aplikacja pokazuje pierwszy odnaleziony fragment jako odpowiedź wyciągową z jego źródłem. Przy awarii embeddingów informuje o niedostępności, zamiast zastępować wyszukiwanie nieoznaczoną wiedzą modelu.

To ogranicza ryzyko prompt injection, ale nie stanowi matematycznej gwarancji zgodności każdej wypowiedzi ze źródłem. Nie dodawaj niezweryfikowanych dokumentów do zatwierdzonej bazy. Nadal potrzebna jest ocena odpowiedzi, zwłaszcza pytań złożonych i odmian językowych.

## MLflow i testy

W eksperymencie `roboinspect-bielik`, w Runs, dla odpowiedzi RAG zapisujemy: `rag_used`, dostępność, czas wyszukiwania, liczbę fragmentów, wynik najlepszego dopasowania i odmowę odpowiedzi. Artefakt `retrieval.json` zawiera użyte fragmenty i wersję dokumentów. `interaction.json` zachowuje pytanie, odpowiedź i interpretację. Numer wersji wag embeddingów jest zapisany przy wyszukiwaniu; MLflow nie jest wymagany do zatrzymania robota.

```bash
PYTHONPATH=src .venv/bin/python scripts/check_rag.py --answers
bash scripts/test_project.sh -q
```

Pierwsza komenda wymaga uruchomionego kokpitu. Wykonuje wyszukiwanie i opcjonalnie odpowiedzi na pytania testowe bez tworzenia misji. Eksperyment `roboinspect-rag-evaluation` zawiera metryki i artefakt `evaluation.json`. Wynik kontrolny jest także w `docs/verification/rag-evaluation.json`.

Zestaw 20 pytań jest małym zestawem kontrolnym używanym również podczas dopracowania rozwiązania. Nie jest niezależnym testem generalizacji. Trafne znalezienie źródła nie oznacza automatycznie poprawnej odpowiedzi. Przed oceną końcową należy dodać osobny zestaw pytań i ręczną ocenę zgodności ze źródłem.

Źródła techniczne: [API embeddingów Ollama](https://docs.ollama.com/api/embed), [EmbeddingGemma 300M i licencja](https://ollama.com/library/embeddinggemma:300m). SHA256 wag: `0800cbac9c2064dde519420e75e512a83cb360de3ad5df176185dc69652fc515`.
