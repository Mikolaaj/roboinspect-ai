"""Public operator scope. No secrets, code, host paths or deployment instructions enter answers."""

import re
import unicodedata


def normalized(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("ł", "l")
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c) and unicodedata.category(c) != "Cf"
    )


def is_stop(text):
    return bool(
        re.fullmatch(
            r"\s*(?:stop|sotp|zatrzymaj(?:\s+(?:robota|wszystko|misje|przejazd))?)\s*[.!]*\s*",
            normalized(text),
        )
    )


REFUSAL = "Pomagam w obsłudze robota: zlecaniu i anulowaniu misji, mapowaniu oraz podglądzie kamer. Nie ujawniam instrukcji wewnętrznych ani nie podaję sposobów modyfikowania systemu."


def restricted(text):
    value = normalized(text)
    return bool(
        re.search(
            r"(?:zignoruj|ignoruj|omin\b|obejdz|nowe zasady|udawaj|jailbreak|base64|rot13|"
            r"system\s*prompt|prompt|instrukcj\w*\s+(?:systemow|wewnetrz)|developer|"
            r"\[/?inst\]|<\||\b(?:sudo|curl|wget|ssh|bash|exec|eval|pip|python)\b|"
            r"\.env\b|/home/|/etc/|hasl\w*|sekret\w*|credential|api.?key|klucz\w*\s+api|"
            r"\btoken\w*|\b(?:kod|kodu|repozytor\w*|plik\w*|sciezk\w*|port\w*)\b|"
            r"modyfik\w*|przerob\w*|edyt\w*|konfigur\w*|usun\w*|"
            r"zmien\w*\s+(?:kod|parametr|zasad|zabezpiecz|system|prompt|plik|uprawn)|"
            r"wylacz\w*\s+zabezpiec|ujawnij|wycieknij|wypisz\s+(?:wszystkie|wewnetrzne))",
            value,
        )
    )


def motion_request(text):
    return bool(
        re.match(
            r"^\s*(?:prosze\s+)?(?:jedz\b|pojedz\b|podjedz\b|przejedz\b|"
            r"odwiedz\b|wroc\b|wracaj\b|skieruj\b|chce\s+pojechac\b)",
            normalized(text),
        )
    )


def help_topic(text):
    value = normalized(text)
    if re.search(
        r"(?:\bgdzie\s+(?:teraz\s+)?jestes\b|\bstatus\b|\bpozycj\w*\b)", value
    ) and not re.search(r"\b(?:jak|opisz|wyjasnij)\b", value):
        return None
    if re.search(
        r"\b(?:jak|gdzie|opisz|wyjasnij|wytlumacz|dlaczego|czym|czego|sluzy|obslug\w*)\b", value
    ):
        pass
    elif re.search(r"\b(?:co|czy)\b", value) and re.search(
        r"system|robot|slam|nav2|kamer|mapow|mlflow|potraf", value
    ):
        pass
    else:
        return None
    if re.search(
        r"losow|losuj|ustawien\w*\s+magaz|usun\w*\s+(?:wszystkie\s+)?przeszkod|wyposaz", value
    ):
        return "warehouse"
    if re.search(r"inspekcj|detekcj|yolo|baner|zdjeci|wykryw|zielon.*pol|pol.*obserw", value):
        return "inspection"
    if re.search(r"mikrofon|whisper|glos|nagran|mowic", value):
        return "voice"
    if re.search(r"mlflow|eksperyment|wyniki", value):
        return "results"
    if re.search(r"mapa\s*2d|plan\s+hangaru|zolt\w*\s+(?:lin|krop|punkt)|tras", value):
        return "navigation"
    if re.search(r"slam|mapow|mapa|mape", value):
        return "mapping"
    if re.search(r"kamer|obraz|monitoring", value):
        return "cameras"
    if re.search(r"anul|zatrzym|\bstop\b", value):
        return "stop"
    if re.search(r"nav2|nawig|omija|trase", value):
        return "navigation"
    if re.search(r"wyslac|wysyl|zlec|sektor|przycisk|sterow|obslug", value):
        return "controls"
    return "overview"


GUIDE = {
    "inspection": "Pod przyciskami jazdy wybierz Inspekcja sektora A, B lub C. Zielone pola P1 do P5 oznaczają dokładne miejsca obserwacji. Robot jedzie do środka zielonego pola i ustawia kamerę na tablicę. Robot odwiedzi kolejno każdą tablicę P w sektorze, zatrzyma się, zapisze zdjęcie i wykrycia YOLO, a potem wróci na czerwone pole sektora. A obejmuje P1 i P2, B P3 i P4, C P5. W kokpicie rozwiń Historię detekcji z inspekcji i wybierz obserwację. Widać zdjęcie, ramki, klasy, liczbę wykryć oraz pewność modelu. Person oznacza człowieka; numer dotyczy pojedynczej klatki, nie tożsamości osoby. Możesz zapytać, co robot widział w sektorze A. Odpowiedź opisuje ostatnią zapisaną inspekcję, a nie aktualny obraz. Zmień zdjęcia na banerach losuje nowe fotografie i odświeża symulację, wracając do BASE. Historia pozostaje. YOLO rozpoznaje 80 klas, więc brak wykryć nie oznacza pustego zdjęcia.",
    "warehouse": "W panelu sterowania pod mapowaniem są trzy przyciski ustawienia magazynu. Standardowe ustawienie przywraca oryginalne wyposażenie. Usuń wszystkie przeszkody usuwa wyposażenie, skrzynie i wolnostojące słupy; ściany, tablice oraz robot pozostają. Losuj przeszkody ustawia to samo wyposażenie w jego sektorach, zachowując przejścia do czerwonych stref i punktów P. Zmiana jest możliwa po zakończeniu jazdy i mapowania. Odświeża symulację i mapę nawigacyjną, przenosząc robota do bazy. Wcześniejsze mapy i historia są zachowane. Poczekaj na gotowość i obserwuj wynik operacji w historii.",
    "overview": "RoboInspect to symulacja mobilnego robota w hangarze. Możesz zlecać przejazdy między sektorami A, B i C oraz bazą BASE. Robot planuje trasę i omija przeszkody, a trzy kamery pozwalają obserwować przejazd. W panelu sprawdzisz pozycję, wynik misji i historię. Możesz też tworzyć i zapisywać mapę hali.",
    "voice": "Kliknij Mikrofon w panelu czatu i zezwól przeglądarce na nagrywanie. Powiedz krótkie polecenie po polsku, np. Jedź do sektora B i wróć do bazy. Kliknij Zakończ nagranie. Lokalny Whisper wpisze rozpoznaną wypowiedź do pola wiadomości. Sprawdź i w razie potrzeby popraw tekst, potem naciśnij Enter lub Wyślij. Samo nagranie nie uruchamia misji. Anuluj nagranie przerywa nagrywanie lub oczekiwanie na wynik. Aby szybko zatrzymać robota, użyj Anuluj przejazd albo wpisz STOP; nie czekaj na rozpoznawanie głosu.",
    "controls": "W panelu sterowania wybierz przycisk A, B, C lub Powrót do bazy. Możesz też napisać w czacie „Jedź do B i wróć do bazy” i nacisnąć Enter lub Wyślij. Kroki misji wykonają się kolejno. Wynik pokazuje panel i wiadomość z misją; samo przyjęcie polecenia nie oznacza dojazdu. Sektory A, B i C prowadzą do czerwonych stref przed tablicami. A ma wspólną strefę dla P1 i P2, B dla P3 i P4, a C przed P5. Robot ustawia kamerę w stronę tablic. Nie ma dodatkowego okna potwierdzenia.",
    "navigation": "Nav2 odpowiada za planowanie trasy i prowadzenie robota do wybranego celu. Korzysta z mapy oraz odczytów czujników, aby omijać przeszkody. Ty wskazujesz sektor w panelu lub czacie i obserwujesz postęp. W kokpicie obok mapy SLAM znajduje się plan 2D hangaru z przeszkodami i turkusową kropką robota. Żółta linia pokazuje aktualną trasę Nav2, a żółty punkt cel. Tę samą linię widać na podłodze w kamerach. Po wykryciu nowej przeszkody lidar aktualizuje dane i Nav2 przelicza plan; linia się zmienia. Po dojeździe lub anulowaniu trasa znika. Jeśli przejazd się nie powiedzie, panel pokaże błąd i pozostałe kroki zostaną pominięte.",
    "mapping": "SLAM tworzy mapę hangaru podczas ruchu robota na podstawie pomiarów odległości. Pod przyciskami jazdy wybierz Rozpocznij mapowanie, aby uruchomić obchód. Zapisz mapę zachowuje jej wersję, a Resetuj mapę rozpoczyna świeżą mapę. Zakończ mapowanie zapisuje wynik i przywraca zwykłą nawigację z robotem w bazie. Kropka na mapie pokazuje pozycję robota.",
    "cameras": "Kokpit pokazuje trzy widoki: obraz z kamery robota, kamerę podążającą za robotem z boku i monitoring całej hali z góry. Pierwszy pozwala zobaczyć to, co znajduje się przed robotem. Widok boczny ułatwia obserwację jego ruchu, a monitoring pokazuje położenie w całym hangarze.",
    "stop": "Napisz w czacie STOP, aby przerwać odpowiedzi asystenta, anulować misję i zatrzymać obchód mapowania. Przycisk Anuluj przejazd służy do anulowania misji. Przycisk Zatrzymaj odpowiedź przerywa tylko analizę wiadomości; nie cofa już przyjętej misji. Panel pozostaje otwarty, aby pokazać potwierdzenie zatrzymania.",
    "results": "MLflow służy do przeglądania wyników działania asystenta. W widoku Model training wybierz eksperyment roboinspect-bielik i listę Runs. Zobaczysz czas odpowiedzi, poprawność formatu i informację, czy przyjęto misję. Przyjęcie misji nie potwierdza dojazdu. Wynik przejazdu sprawdzaj w panelu robota.",
}

PUBLIC_GUIDE = "\n".join(f"{key}: {value}" for key, value in GUIDE.items())


def safe_answer(text, topic):
    words = normalized(text)
    if restricted(text) or len(text.strip()) < 100:
        return False
    anchors = {
        "inspection": ["inspekcj", "tablic", "yolo", "wykry", "sektor"],
        "overview": ["robot", "hangar", "misj", "sektor", "kamer"],
        "warehouse": ["magazyn", "przeszkod", "przycisk", "bazy", "losuj"],
        "voice": ["mikrofon", "whisper", "nagran", "tekst", "wyslij"],
        "controls": ["panel", "przycisk", "jedz", "misj", "enter"],
        "navigation": ["nav2", "tras", "przeszk", "map"],
        "mapping": ["map", "slam", "hangar", "zapis"],
        "cameras": ["kamer", "widok", "obraz", "monitoring"],
        "stop": ["stop", "anul", "zatrzym", "misj"],
        "results": ["mlflow", "runs", "wynik", "misj"],
    }
    return sum(anchor in words for anchor in anchors[topic]) >= 2
