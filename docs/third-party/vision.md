# Modele i zdjęcia inspekcji

## YOLO11s

Źródło kodu i dokumentacji: https://github.com/ultralytics/ultralytics oraz https://docs.ultralytics.com/models/yolo11/.

Oficjalne wagi: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt
SHA256: `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`.

Ultralytics udostępnia kod i modele na licencji AGPL-3.0 oraz licencji komercyjnej Enterprise. Ta integracja używa otwartego wariantu AGPL. Wagi nie są commitowane. Przy dystrybucji lub udostępnianiu większej aplikacji trzeba uwzględnić warunki tego wariantu: https://www.ultralytics.com/license. Plik tego opisu nie zmienia automatycznie licencji pozostałej części repozytorium.

## Fotografie COCO128

Źródło archiwum przykładowego: https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip
SHA256: `61e5e3028863d8ffc3b81d6a514603954889f0edd5e4b44c4ce60b2da99aeb8e`.

Pochodzenie: obrazy COCO train2017, wybrane przez oficjalny przykład COCO128. Informacje o zbiorze i licencjach: https://cocodataset.org/#termsofuse oraz https://docs.ultralytics.com/datasets/detect/coco128/.

Fotografie COCO pochodzą z Flickr; poszczególne zdjęcia zachowują własne licencje, odrębne od licencji adnotacji i kodu. Nie deklarujemy, że wszystkie są w domenie publicznej. Pobierane są lokalnie jako przykłady edukacyjne; oryginały, pochodne tekstury i klatki inspekcji nie trafiają do Git. Manifest `data/vision/photos.json` zapisuje identyfikatory COCO, sumy plików i odnośnik do strony źródłowego zdjęcia w COCO Explorer. Do dalszej publikacji fotografii należy sprawdzić właściwą licencję źródłowego zdjęcia i wymagane przypisanie autorstwa.

Kod wyboru i przygotowania: `scripts/setup_vision_assets.py`. Nie używamy etykiet COCO do wytwarzania odpowiedzi detektora; etykiety są użyte wyłącznie do wyboru różnorodnego zestawu fotografii podczas przygotowania.

## SAM 2.1 Tiny

Wagi z oficjalnego wydania Ultralytics v8.3.0: sam2.1_t.pt, SHA256 `3c1e81ca9b037dd39d70a014ddb9a813d6c4c4e12555420db7eaff31689bd4e3`. [Opis integracji i licencji](../sam.md).
