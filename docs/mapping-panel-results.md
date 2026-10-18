# Panel mapowania i pozycja robota — odbiór 18.10.2026

Wdrożono sterowanie pełnym cyklem SLAM z panelu `/control`, pod przyciskami sektorów.
Standardowe uruchamianie: tylko `run_cockpit.sh` i `run_control_panel.sh`.

Sprawdzone na rzeczywistej symulacji:

- Start i reset podczas jazdy z przycisków panelu: obchód przerwany, robot zatrzymany, oba wpisy w historii.
- Pełny obchód 8 punktów ze zdarzeniami postępu w bazie.
- Zapis, zachowanie poprzedniej wersji po resecie, ponowny zapis i zakończenie mapowania.
- Zakończenie zapisuje mapę, restartuje świat w BASE i uruchamia AMCL/Nav2 bez zamykania API.
- Kropka i kierunek robota na mapie poruszają się z aktualnym TF; pozycja jest przeliczana do pikseli.
- Próba zlecenia misji lub zapisu podczas obchodu jest odrzucana.
- Powtórzenie klucza żądania zwraca ten sam wpis zamiast ponawiać operację.
- Po zwykłym restarcie zachowano historię i automatycznie wybrano mapę zapisaną przy zakończeniu.
- Trzy kamery, anulowanie misji i przejazdy na zapisanej mapie po restarcie:

| Cel | Wynik | Błąd względem pozycji Gazebo |
|---|---|---|
| A | succeeded | 0.105 m |
| BASE | succeeded | 0.063 m |

Testy aplikacji: 39 zaliczonych; Ruff check i format poprawne.
Jedno ostrzeżenie zależności Starlette o przyszłej zmianie klienta testowego.
Testy obejmują również anulowanie podczas przełączania, brak ponowienia ruchu
po restarcie, zapis błędu i zwolnienie zasobu oraz obrót/origin/odwrócenie osi mapy.

Raporty: [pełny cykl](verification/mapping-panel.json),
[restart](verification/mapping-panel-restart.json),
[nawigacja](verification/mapping-panel-navigation.json).

Zakres: kontrolowany obchód standardowej hali. Reset zachowuje pliki zapisanych
map i historię. Obsługa nie wymaga dodatkowych poleceń ROS ani ręcznego przełączania
SLAM/Nav2. Szczegóły: [slam.md](slam.md).
