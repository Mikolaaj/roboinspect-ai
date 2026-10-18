# Lokalny czat LLM — stan wdrożenia

Wybrano Bielik 4.5B v3.0 Instruct, kwantyzacja Q4_K_M, lokalne Ollama.
Zaimplementowano zapisywaną rozmowę po prawej stronie panelu, interpretację
ustrukturyzowanych odpowiedzi, walidację Pydantic i przekazanie do MissionService.
Używamy bezpośredniego API Ollama z JSON Schema; biblioteka Pydantic AI nie jest
obecnie zależnością projektu.

MLflow zapisuje interakcje i eksperymenty, a oddzielny skrypt ewaluacji porównuje
intencje i cele ze wzorcem bez uruchamiania ruchu. Instrukcja: [bielik-chat.md](bielik-chat.md).
Raport sprawdzenia: [bielik-results.md](bielik-results.md).

Późniejsze fazy: mikrofon/Whisper, RAG, YOLO oraz SAM, dalsze profilowanie i
zarządzanie pamięcią GPU. Nie są jeszcze częścią działającego czatu tekstowego.
