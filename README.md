# TagForge (ComfyUI)

Tag Translator, autouzupełnianie tagów i baza artystów dla modeli **Anima** i **Illustrious**.

## Start
1. Zbuduj bazę tagów (Danbooru API + e621 db_export, kilka minut, kilkadziesiąt MB):
   `..\..\.venv\Scripts\python.exe scripts\build_db.py`
2. Zrestartuj ComfyUI.

Bez bazy działają tylko składnia i blokada.

## Node'y
- **Tag Translator (TagForge)**: `text` → `text`, `report`.
  - `model`: Anima (`@artysta`, spacje, `score_N` z podkreślnikiem) albo Illustrious (artysta bez `@`).
  - `tags_to`: Danbooru albo e621. Tłumaczenie korzysta z aliasów, takich samych nazw i ręcznej tabeli `data/mapping_e621_danbooru.csv`.
  - Nawiasy w nazwach są escape'owane (`pokemon \(creature\)`), bo ComfyUI czyta `(` jako wagę.
  - Zdania (6+ słów albo z kropką) przechodzą bez zmian.
  - `report` pokazuje: nieznane tagi, tłumaczenia, artystów i uwagi. Podepnij go pod `Preview Any`.
- **Artist Picker (TagForge)**: lista artystów albo losowanie. Przycisk „Przeglądaj artystów…” otwiera listę z wyszukiwarką.

## Autouzupełnianie (Tag Builder)
Działa w każdym polu tekstowym: ↑/↓, Enter/Tab, Esc.
- Po wyjściu z pola: pomarańczowa ramka = nieznane tagi, czerwona = zablokowane. Lista jest w dymku po najechaniu.
- Ustawienia: *Settings → TagForge* (model, źródło podpowiedzi, wł./wył.).

## Artyści
- Lista artystów z Danbooru (z ≥100 postami), posortowana po liczbie postów.
- Wyszukiwarka, link do profilu na Danbooru, kliknięcie w wiersz dopisuje artystę w składni modelu.
- Losowanie (`random_count`) bierze tylko artystów, których tag powstał przed końcem danych modelu:
  - Anima: wrzesień 2025, z karty modelu.
  - Illustrious: koniec 2023 (Danbooru2023); karta nie podaje daty.

## Blokada
Tagi i słowa oznaczające nieletnich (loli, shota, cub, young, child…, wiek < 18) zatrzymują generowanie. Nie da się tego wyłączyć.

## Test
`..\..\.venv\Scripts\python.exe tests\test_core.py`
