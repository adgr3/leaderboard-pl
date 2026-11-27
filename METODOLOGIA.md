# Metodologia

## Schemat rekordu

Każdy plik w wyniki/*.json musi być zgodny ze schema/wynik.schema.json.

Pola wymagane:

| Pole | Typ | Opis |
|---|---|---|
| model | string | Nazwa modelu/tokenizera. |
| model_revision | string/null | Rewizja modelu (commit/tag), jeśli znana. |
| family | string | Rodzina/model group (np. Slayer, Bielik, Tokenizer). |
| benchmark | string | Nazwa benchmarku po normalizacji aliasów. |
| benchmark_version | string/null | Wersja benchmarku/datasetu. |
| data_revision | string/null | Rewizja danych wejściowych. |
| subset | string/null | Podzbiór/split, np. full test set. |
| metric | string | Nazwa metryki. |
| score | number/null | Wynik; 
ull tylko gdy status=null. |
| stderr | number/null | Błąd standardowy, jeśli dostępny. |
| ci95 | object/null | Przedział ufności 95%, jeśli dostępny. |
| 
 | integer/null | Liczba przykładów. |
| 
_empty | integer/null | Liczba pustych odpowiedzi, jeśli dotyczy. |
| 
_overflow | integer/null | Liczba przepełnień/ucięć kontekstu, jeśli dotyczy. |
| settings | object | Ustawienia uruchomienia (decode, prompt, wariant itp.). |
| harness | string/object/null | Narzędzie uruchomieniowe. |
| judge | string/object/null | Sędzia/ewaluator, jeśli dotyczy. |
| deviations | array[string] | Odstępstwa od protokołu. |
| comparable_to_reference | object | {comparable: bool, reason: string}. |
| source | object | Pochodzenie wyniku. |
| measured_by | enum | adgr3, bench-team, model-card. |
| date | string/null | Data pomiaru/pozyskania. |
| status | enum | measured lub 
ull. |
| 
ull_reason | string/null | Wymagany powód dla status=null. |

### status i 
ull_reason

- status="measured": pomiar wykonany; score jest liczbą.
- status="null": brak wyniku; score musi być 
ull, a 
ull_reason musi być niepustym stringiem.
- 
ot run używamy w prezentacji, gdy 
ull_reason opisuje niewykonanie benchmarku (np. brak okna kontekstu, brak narzędzi, decyzja maintainera). W danych źródłem prawdy jest status=null + 
ull_reason.

### source

source identyfikuje plik źródłowy:

- 
epo — repozytorium/źródło logiczne.
- path — ścieżka do pliku źródłowego w tym repo.
- commit — commit źródła, jeśli dostępny.
- sha256 — SHA-256 pliku źródłowego.
- url — link do źródła, jeśli dostępny.
- pr_status — opcjonalny status PR.

## Skąd biorą się liczby

Liczby w leaderboard.md i docs/wszystkie_rekordy.md są generowane wyłącznie z wyniki/*.json przez scripts/buduj.py. Generator oblicza SHA-256 danych z nazw i zawartości plików wyniki/*.json i zapisuje go w stopce. python scripts/buduj.py --check sprawdza, czy wygenerowane pliki są aktualne.

Każdy rekord musi wskazywać źródło. Dla rekordów z repozytoriów zewnętrznych source.sha256 odnosi się do pliku źródłowego w tamtym repozytorium; weryfikacja testem jest wykonywana, gdy lokalne _zrodla/ jest dostępne.

## Normalizacja

- Nazwy benchmarków są normalizowane przez schema/aliasy.json.
- Metryki dokładności/pass-rate są prezentowane jako procenty, gdy skala i typ metryki na to wskazują.
- Metryki nieprocentowe (BPB, perplexity, fertility, bytes/token) nie są zamieniane na procenty.
- Odchylenie standardowe/CI jest pokazywane tylko wtedy, gdy istnieje w źródle. Brak takiej informacji jest oznaczany jako — w opisie, nie jako sztuczna wartość.

## Porównywalność

Porównanie jest uzasadnione tylko przy zgodnym benchmarku, metryce, podzbiorze, ustawieniach i procedurze oceny. Odstępstwa zapisujemy w deviations. Pole comparable_to_reference opisuje, czy wynik można porównywać z referencją i dlaczego.

## Źródła i metodologia Bench

Szczegółowa metodologia dla benchmarków zespołu Bench jest w repozytorium źródłowym:
[slayerlabs/benchmarks-fabryka-ai: research/METHODOLOGY.md](https://github.com/slayerlabs/benchmarks-fabryka-ai/blob/main/research/METHODOLOGY.md)
