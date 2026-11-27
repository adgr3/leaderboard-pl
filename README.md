# leaderboard-pl

## Polski

`leaderboard-pl` to publiczne repozytorium z wynikami benchmarków modeli językowych, zebranymi w ujednoliconym formacie JSON. Każdy rekord ma źródło, metadane uruchomienia i jest walidowany schematem. Tabela `leaderboard.md` jest generowana skryptem z plików `wyniki/*.json`.

- Hugging Face Space: https://huggingface.co/spaces/adegier/leaderboard-pl
- Hugging Face Dataset: https://huggingface.co/datasets/adegier/leaderboard-pl-results

### Co tu jest

- `wyniki/*.json` — rekordy pomiarów zgodne ze `schema/wynik.schema.json`
- `opisy/benchmarki.yaml` — opisy benchmarków (PL/EN, rodzina, metryka, kierunek, źródło)
- `leaderboard.md` — wygenerowany widok główny (ranking, wykresy, sekcje rodzin)
- `docs/wykresy/*.svg` — deterministyczne wykresy SVG generowane z danych
- `docs/wszystkie_rekordy.md` — pełna lista rekordów
- `scripts/buduj.py` — generator tabel/wykresów i `--check`
- `scripts/eksport_hf.py` — eksport HF dataset/Space i `--check`
- `hf/dataset/` — karta zbioru + `data/results.parquet/jsonl/csv`, `benchmarks.jsonl`
- `hf/space/` — statyczny Space (HTML + `results.json` + `benchmarks.json`)
- `schema/` — schemat JSON i aliasy nazw benchmarków

### Jak czytać znaczniki

- `★` — pomiar zespołu tego projektu (`measured_by=adgr3`)
- `†` — odstępstwo od protokołu / wynik nieporównywalny
- `∅` — brak wyniku (`status=null`) z podanym powodem
- `ⓡ` — wartość z karty modelu / źródła referencyjnego (`measured_by=model-card`)
- `—` — brak błędu standardowego lub CI w źródle
- `not run (...)` — benchmark nie był uruchamiany; powód jest w nawiasie

Wyniki dokładności/pass-rate są normalizowane do procentów (0–100, 1 miejsce po przecinku), gdy metryka tego wymaga. Metryki nieprocentowe (np. BPB, perplexity, fertility, bytes/token) pozostają w oryginalnej skali.

### Zasady porównań

Porównuj tylko wyniki, które mają ten sam benchmark, tę samą metrykę i zgodne ustawienia. Różnice w prompcie, szablonie czatu, decode, judge, długości kontekstu, liczbie prób, podzbiorze danych lub harnessie mogą unieważnić porównanie. Odstępstwa muszą być opisane w polu `deviations`, a brak porównywalności w `comparable_to_reference`.

### Jak dodać wynik

1. Dodaj plik JSON do `wyniki/`, zgodny ze `schema/wynik.schema.json`.
2. Uzupełnij źródło (`source.repo`, `source.path`, `source.commit`, `source.sha256`, opcjonalnie `source.url`).
3. Ustaw `status`: `measured` dla realnego pomiaru albo `null` z `null_reason`.
4. Wygeneruj tabele/wykresy: `python scripts/buduj.py`.
5. Wygeneruj eksport HF: `python scripts/eksport_hf.py`.
6. Sprawdź spójność: `python scripts/buduj.py --check` i `python scripts/eksport_hf.py --check`.
7. Uruchom testy: `python -m pytest -q`.

### Licencje danych

Kod w tym repozytorium jest objęty licencją MIT (`LICENSE`). Kompilacja danych w tym repozytorium jest udostępniana jako CC-BY-4.0, z zastrzeżeniem, że wyniki pochodzą z wymienionych źródeł i mogą podlegać ich własnym warunkom:

| Źródło | Licencja | Uwagi |
|---|---|---|
| `slayerlabs/benchmarks-fabryka-ai` | unknown | W lokalnym źródle `_zrodla/benchmarks-fabryka-ai` nie znaleziono pliku `LICENSE`; repo zawiera metadane i linki do wyników. |
| `adgr3/tokenizatorex` | unknown | W lokalnym źródle `_zrodla/tokenizatorex` nie znaleziono pliku `LICENSE`; rekordy zawierają metadane i linki do plików wynikowych. |
| `local:bielik-if-pl` | unknown | Lokalny zestaw ewaluacyjny; w repo nie ma jawnego pliku licencji dołączonego do tych wyników. |

Przed ponownym użyciem danych sprawdź licencję i warunki źródła pierwotnego.

## English

`leaderboard-pl` is a public repository of language-model benchmark results collected in a unified JSON format. Every record includes provenance, run metadata, and is validated against a schema. `leaderboard.md` is generated from `wyniki/*.json`.

- Hugging Face Space: https://huggingface.co/spaces/adegier/leaderboard-pl
- Hugging Face Dataset: https://huggingface.co/datasets/adegier/leaderboard-pl-results

### Contents

- `wyniki/*.json` — measurement records conforming to `schema/wynik.schema.json`
- `leaderboard.md` — generated main view
- `docs/wszystkie_rekordy.md` — full record list
- `scripts/buduj.py` — table generator and `--check` verification mode
- `schema/` — JSON schema and benchmark name aliases

### Markers

- `★` — measured by this project (`measured_by=adgr3`)
- `†` — protocol deviation / not comparable
- `∅` — missing result (`status=null`) with reason
- `ⓡ` — model-card/reference value (`measured_by=model-card`)
- `—` — missing standard error/CI in source
- `not run (...)` — benchmark was not executed; reason in parentheses

Accuracy/pass-rate results are normalized to percent (0–100, 1 decimal place) when appropriate. Non-percent metrics (e.g. BPB, perplexity, fertility, bytes/token) keep their original scale.

### Comparison rules

Compare only results with the same benchmark, metric, and compatible settings. Differences in prompt, chat template, decoding, judge, context length, sample count, data subset, or harness can invalidate comparison. Deviations must be recorded in `deviations`, and non-comparability in `comparable_to_reference`.

### Adding a result

1. Add a JSON file to `wyniki/` conforming to `schema/wynik.schema.json`.
2. Fill source fields (`source.repo`, `source.path`, `source.commit`, `source.sha256`, optional `source.url`).
3. Set `status`: `measured` for an actual run, or `null` with `null_reason`.
4. Generate tables: `python scripts/buduj.py`.
5. Verify consistency: `python scripts/buduj.py --check`.
6. Run tests: `python -m pytest -q`.

### Data licenses

Code in this repository is MIT-licensed (`LICENSE`). The compiled dataset in this repository is published as CC-BY-4.0, while underlying results come from the listed sources and may have their own terms:

| Source | License | Notes |
|---|---|---|
| `slayerlabs/benchmarks-fabryka-ai` | unknown | No `LICENSE` file found in local `_zrodla/benchmarks-fabryka-ai`; repository stores metadata and links to results. |
| `adgr3/tokenizatorex` | unknown | No `LICENSE` file found in local `_zrodla/tokenizatorex`; records store metadata and links to result files. |
| `local:bielik-if-pl` | unknown | Local evaluation set; no explicit license file attached to these results in this repo. |

Check the original source license and terms before reusing data.
