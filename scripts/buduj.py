import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WYNIKI = ROOT / "wyniki"
OUT = ROOT / "leaderboard.md"
DOCS = ROOT / "docs"
ALL_REC = DOCS / "wszystkie_rekordy.md"
SLAYER_SVG = DOCS / "slayer_checkpointy.svg"
ALIASES = ROOT / "schema" / "aliasy.json"


def load_aliases():
    if ALIASES.exists():
        return json.loads(ALIASES.read_text(encoding="utf-8")).get("aliases", {})
    return {}


ALIASES_MAP = load_aliases()

PERCENT_METRICS = {
    "acc", "acc_norm", "accuracy", "pass_rate", "prompt_level_strict_acc",
    "prompt_level_loose_acc", "instruction_level_strict_acc", "instruction_level_loose_acc",
    "prompt_level_strict", "prompt_level_loose", "instruction_level_strict", "instruction_level_loose",
    "overall_acc", "exact_match (flexible-extract)",
}
PERCENT_BENCH_HINTS = ("ifeval", "ifbench", "ifstruct", "multi-if", "bfcl", "automationbench", "aa-omniscience", "aa-lcr", "ruler", "hle", "terminal-bench", "humanity")


def norm_bench(name):
    return ALIASES_MAP.get(name, name)


def data_sha():
    h = hashlib.sha256()
    for p in sorted(WYNIKI.glob("*.json")):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def load_records():
    recs = []
    for p in sorted(WYNIKI.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["benchmark"] = norm_bench(d.get("benchmark"))
        recs.append(d)
    return recs


def is_percent(r):
    m = (r.get("metric") or "").lower()
    b = (r.get("benchmark") or "").lower()
    if "byte_perplexity" in m or "perplexity" in m or "bytes per token" in m or "fertility" in m:
        return False
    if m in PERCENT_METRICS or "acc" in m or "pass" in m or "accuracy" in m:
        s = r.get("score")
        if s is None:
            return "percent" in b or any(h in b for h in PERCENT_BENCH_HINTS)
        if 0 <= s <= 1.5:
            return True
        if 0 <= s <= 100:
            return any(h in b for h in PERCENT_BENCH_HINTS) or "percent" in m
    return False


def fmt_score(r):
    if r.get("status") == "null" or r.get("score") is None:
        reason = r.get("null_reason") or "brak powodu"
        reason = reason.replace("|", "/")
        if "not run" in reason.lower():
            low = reason.lower()
            idx = low.find("not run")
            rest = reason[idx + len("not run"):].strip(" -—")
            if rest:
                return f"not run ({rest})"
            return "not run"
        return f"null ({reason})"
    v = r["score"]
    pct = is_percent(r)
    scaled = pct and 0 <= v <= 1.5
    if scaled:
        v = v * 100
    if pct:
        base = f"{v:.1f}%"
    else:
        if abs(v) >= 100 or float(v).is_integer():
            base = f"{v:.4g}" if not float(v).is_integer() else f"{int(v)}" if abs(v) < 10000 else f"{v:.4g}"
        else:
            base = f"{v:.4f}".rstrip("0").rstrip(".")
    se = r.get("stderr")
    ci = r.get("ci95")
    b = (r.get("benchmark") or "").lower()
    metric = (r.get("metric") or "").lower()
    if "token" in b or "fertility" in metric or "bytes per token" in metric:
        return base
    if se is not None and se != 0:
        if scaled and 0 <= se <= 1.5:
            se_v = se * 100
        else:
            se_v = se
        return f"{base} ± {se_v:.2f}" if pct else f"{base} ± {se_v:.4f}".rstrip("0").rstrip(".")
    if ci:
        return base
    return base


def src_link(r):
    s = r.get("source", {})
    url = s.get("url")
    path = s.get("path", "")
    label = path.split("/")[-1] if path else "źródło"
    if url and url.startswith("http"):
        return f"[{label}]({url})"
    if url and url.startswith("local://"):
        return f"{label} (lokalnie)"
    return label


def flag(r):
    f = []
    if r.get("measured_by") == "adgr3":
        f.append("★")
    if r.get("deviations"):
        f.append("†")
    if r.get("status") == "null":
        f.append("∅")
    if r.get("measured_by") == "model-card":
        f.append("ⓡ")
    return "".join(f)


def sort_key_model(m):
    ml = m.lower()
    if ml.startswith("slayer"):
        return (0, ml)
    if ml.startswith("bielik"):
        return (1, ml)
    if ml.startswith("lfm"):
        return (2, ml)
    return (3, ml)


def family_group(model):
    m = model.lower()
    if m.startswith("slayer"):
        return "Slayer"
    if m.startswith("bielik"):
        return "Bielik"
    if m.startswith("lfm"):
        return "LFM"
    return "Inne"


def is_tokenizer_record(r):
    b = (r.get("benchmark") or "").lower()
    m = (r.get("metric") or "").lower()
    return "token fertility" in b or "bytes per token" in b or "fertility" in m


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        cells = ["—" if c is None else str(c).replace("\n", " ").replace("|", "/") for c in row]
        out.append("| " + " | ".join(cells) + " |")
    return out


def build_slayer_svg(records):
    slayer = [r for r in records if r.get("model", "").lower().startswith("slayer") and r.get("status") == "measured" and not is_tokenizer_record(r)]
    by_bench = defaultdict(list)
    for r in slayer:
        by_bench[r["benchmark"]].append(r)
    benchs = [b for b, rs in by_bench.items() if len({x["model"] for x in rs}) >= 2]
    benchs = sorted(benchs)[:8]
    if not benchs:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="80"><text x="10" y="40" font-size="14">Brak danych checkpointów do wykresu.</text></svg>'
        SLAYER_SVG.write_text(svg, encoding="utf-8")
        return
    models = sorted({r["model"] for r in slayer if r["benchmark"] in benchs}, key=lambda m: sort_key_model(m))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
    W, H = 900, 360
    pad_l, pad_r, pad_t, pad_b = 60, 220, 30, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    series = []
    for i, b in enumerate(benchs):
        pts = []
        vals = []
        for m in models:
            rs = [r for r in by_bench[b] if r["model"] == m]
            if not rs:
                continue
            v = rs[0]["score"]
            if v is None:
                continue
            if is_percent(rs[0]) and 0 <= v <= 1.5:
                v = v * 100
            vals.append((m, v, rs[0]))
        if not vals:
            continue
        vmin = min(v for _, v, _ in vals)
        vmax = max(v for _, v, _ in vals)
        span = (vmax - vmin) or 1.0
        for m, v, r in vals:
            x = pad_l + (models.index(m) / (max(1, len(models) - 1))) * plot_w
            y = pad_t + (1 - (v - vmin) / span) * plot_h
            pts.append((x, y, m, v))
        series.append((b, colors[i % len(colors)], pts))
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial,sans-serif">')
    lines.append('<rect width="100%" height="100%" fill="white"/>')
    lines.append('<text x="60" y="20" font-size="14" font-weight="bold">Slayer – postęp po checkpointach (znormalizowany per benchmark)</text>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" stroke="#333"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" stroke="#333"/>')
    for i, m in enumerate(models):
        x = pad_l + (i / (max(1, len(models) - 1))) * plot_w
        lines.append(f'<text x="{x}" y="{H - 20}" font-size="10" text-anchor="middle">{m.replace("slayer", "s")}</text>')
        lines.append(f'<line x1="{x}" y1="{pad_t + plot_h}" x2="{x}" y2="{pad_t + plot_h + 4}" stroke="#333"/>')
    for b, color, pts in series:
        if len(pts) >= 2:
            d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)
            lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        for x, y, _, v in pts:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
    ly = 40
    for b, color, pts in series:
        lines.append(f'<rect x="{W - pad_r + 10}" y="{ly - 10}" width="12" height="12" fill="{color}"/>')
        label = b[:28] + ("…" if len(b) > 28 else "")
        lines.append(f'<text x="{W - pad_r + 28}" y="{ly}" font-size="11">{label}</text>')
        ly += 18
    lines.append('</svg>')
    SLAYER_SVG.parent.mkdir(parents=True, exist_ok=True)
    SLAYER_SVG.write_text("\n".join(lines), encoding="utf-8")


def build():
    records = load_records()
    DOCS.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).date().isoformat()
    sha = data_sha()
    by_mb = Counter(r.get("measured_by") for r in records)
    adgr3 = [r for r in records if r.get("measured_by") == "adgr3"]
    bench_team = [r for r in records if r.get("measured_by") == "bench-team"]
    model_card = [r for r in records if r.get("measured_by") == "model-card"]

    lines = []
    lines.append("# Leaderboard PL")
    lines.append("")
    lines.append("To repo zbiera wyniki benchmarków modeli w jednej, generowanej tabeli. Każdy rekord ma źródło (repo/ścieżka/commit/SHA256) i jest walidowany schematem. Główna sekcja pokazuje tylko pomiary tego projektu (`adgr3`); wyniki innych autorów z repo Bench są osobno, z linkami do źródeł. Nie ma ręcznie wpisanych liczb: `scripts/buduj.py --check` sprawdza spójność.")
    lines.append("")
    lines.append(f"Wygenerowano: {now}  ")
    lines.append(f"Dane (SHA-256): `{sha}`  ")
    lines.append(f"Liczba rekordów: {len(records)} (adgr3: {by_mb.get('adgr3', 0)}, bench-team: {by_mb.get('bench-team', 0)}, model-card: {by_mb.get('model-card', 0)})  ")
    lines.append("")
    lines.append("## Jak czytać")
    lines.append("")
    lines.append("- `★` nasz pomiar (`measured_by=adgr3`), `†` odstępstwo/protokół nieporównywalny, `∅` null z powodem, `ⓡ` wartość z karty modelu.")
    lines.append("- Wyniki dokładności/pass są pokazane w % (0–100, 1 miejsce po przecinku), chyba że metryka jest z natury inna (BPB, perplexity, fertility, bytes/token).")
    lines.append("- `—` oznacza brak błędu standardowego/CI w źródle. Tokenizery są w osobnej tabeli bez `±`.")
    lines.append("- Porównuj tylko wiersze z tym samym benchmarkiem, metryką i podobnymi ustawieniami; odstępstwa są w sekcji „Odstępstwa i znane problemy”.")
    lines.append("")

    lines.append("## Przegląd (nasze pomiary)")
    lines.append("")
    if adgr3:
        bench_counts = Counter(r["benchmark"] for r in adgr3 if r.get("status") == "measured" and not is_tokenizer_record(r))
        key_bench = [b for b, _ in bench_counts.most_common(12)]
        models = sorted({r["model"] for r in adgr3 if not is_tokenizer_record(r)}, key=sort_key_model)
        headers = ["Model"] + key_bench
        rows = []
        for m in models:
            row = [m]
            for b in key_bench:
                rs = [r for r in adgr3 if r["model"] == m and r["benchmark"] == b and r.get("status") in ("measured", "null")]
                if not rs:
                    row.append("—")
                else:
                    r0 = rs[0]
                    row.append(f"{fmt_score(r0)} {flag(r0)} {src_link(r0)}".strip())
            rows.append(row)
        lines.extend(md_table(headers, rows))
    else:
        lines.append("_Brak rekordów adgr3._")
    lines.append("")

    def family_of_benchmark(b):
        bl = (b or "").lower()
        if "token fertility" in bl or "bytes per token" in bl:
            return "tokenizery"
        if any(k in bl for k in ("scicode", "livecode")):
            return "kod"
        if any(k in bl for k in ("arc", "hellaswag", "mmlu", "gpqa", "hle", "humanity", "winogrande", "truthful", "lambada", "wikitext", "gsm", "math", "medmcqa", "pubmedqa", "social-iqa")):
            return "wiedza"
        if any(k in bl for k in ("multiblimp", "blimp", "if-pl", "ifeval", "ifbench", "multi-if", "ifstruct", "polish", "ewok")):
            return "polszczyzna"
        if any(k in bl for k in ("ruler", "aa-lcr", "long")):
            return "dlugi"
        if any(k in bl for k in ("bfcl", "terminal-bench", "automationbench", "tool", "omniscience")):
            return "narzedzia"
        return "inne"

    fam_titles = [
        ("kod", "Kod"),
        ("wiedza", "Wiedza i rozumowanie"),
        ("polszczyzna", "Polszczyzna i instrukcje"),
        ("dlugi", "Długi kontekst"),
        ("narzedzia", "Narzędzia i agenci"),
    ]
    for fam, title in fam_titles:
        sub = [r for r in adgr3 if family_of_benchmark(r["benchmark"]) == fam and not is_tokenizer_record(r)]
        lines.append(f"## {title}")
        lines.append("")
        if not sub:
            lines.append("Brak naszych pomiarów w tej rodzinie.")
            lines.append("")
            continue
        rows = []
        for r in sorted(sub, key=lambda x: (x["benchmark"], sort_key_model(x["model"]), x["metric"])):
            dev = "; ".join(r.get("deviations", [])) or "—"
            set_short = r.get("settings", {}).get("variant") or r.get("subset") or "—"
            rows.append([r["model"], r["benchmark"], r["metric"], fmt_score(r), r.get("n"), r.get("n_empty"), r.get("n_overflow"), set_short, src_link(r), dev])
        lines.extend(md_table(["Model", "Benchmark", "Metryka", "Wynik", "n", "puste", "przepełn.", "Ustawienia", "Źródło", "Odstępstwa"], rows))
        lines.append("")

    lines.append("## Slayer w checkpointach")
    lines.append("")
    slayer = [r for r in records if r.get("model", "").lower().startswith("slayer") and not is_tokenizer_record(r)]
    if slayer:
        build_slayer_svg(records)
        rows = []
        for r in sorted(slayer, key=lambda x: (sort_key_model(x["model"]), x["benchmark"], x["metric"])):
            rows.append([r["model"], r["benchmark"], r["metric"], fmt_score(r), r.get("n"), flag(r), src_link(r)])
        lines.extend(md_table(["Model", "Benchmark", "Metryka", "Wynik", "n", "Flagi", "Źródło"], rows))
        lines.append("")
        lines.append(f"![Slayer checkpointy](docs/{SLAYER_SVG.name})")
        lines.append("")
    else:
        lines.append("_Brak rekordów Slayer._")
        lines.append("")

    lines.append("## Tokenizery")
    lines.append("")
    toks = [r for r in adgr3 if is_tokenizer_record(r)]
    if toks:
        rows = []
        for r in sorted(toks, key=lambda x: (x["benchmark"], x["metric"], x.get("score") if x.get("score") is not None else 1e9)):
            rows.append([r["model"], r["benchmark"], r["metric"], fmt_score(r), r.get("n"), src_link(r)])
        lines.extend(md_table(["Tokenizer/model", "Benchmark", "Metryka", "Wynik", "n", "Źródło"], rows))
    else:
        lines.append("_Brak rekordów tokenizatorów adgr3._")
    lines.append("")

    lines.append("## Odstępstwa i znane problemy")
    lines.append("")
    prob = [r for r in records if r.get("deviations") or r.get("status") == "null"]
    if prob:
        for r in sorted(prob, key=lambda x: (x.get("measured_by", ""), x.get("model", ""), x.get("benchmark", ""))):
            reasons = list(r.get("deviations", []))
            if r.get("status") == "null":
                reasons.append(f"null: {r.get('null_reason')}")
            reason = "; ".join(reasons) if reasons else "—"
            lines.append(f"- [{r.get('measured_by')}] {r.get('model')} / {r.get('benchmark')} / {r.get('metric')}: {reason} ({src_link(r)})")
    else:
        lines.append("- brak")
    lines.append("")

    lines.append("## Kontekst: wyniki zespołu Bench")
    lines.append("")
    if bench_team:
        lines.append("Poniżej są wyniki autorów zespołu Bench w `slayerlabs/benchmarks-fabryka-ai`, powtórzone tutaj wyłącznie z linkami do źródeł. Nie przypisujemy ich temu projektowi; `measured_by=bench-team`. W repo źródłowym nie znaleziono pliku LICENSE, dlatego ta sekcja zawiera tylko metadane i linki, bez kopiowania treści źródłowych.")
        lines.append("")
        rows = []
        for r in sorted(bench_team, key=lambda x: (x["benchmark"], sort_key_model(x["model"]))):
            rows.append([r["model"], r["benchmark"], r["metric"], fmt_score(r), r.get("n"), src_link(r)])
        lines.extend(md_table(["Model", "Benchmark", "Metryka", "Wynik", "n", "Źródło"], rows[:120]))
        if len(rows) > 120:
            lines.append("")
            lines.append(f"_Pokazano 120 z {len(rows)} rekordów bench-team. Pełna lista: [docs/wszystkie_rekordy.md](docs/wszystkie_rekordy.md)._")
    else:
        lines.append("_Brak rekordów bench-team._")
    lines.append("")

    lines.append("## Stopka")
    lines.append("")
    lines.append(f"- Data: {now}")
    lines.append(f"- SHA-256 danych (`wyniki/*.json`): `{sha}`")
    lines.append(f"- Rekordy per measured_by: {dict(by_mb)}")
    lines.append("- Pełna lista: [docs/wszystkie_rekordy.md](docs/wszystkie_rekordy.md)")
    lines.append("")

    main = "\n".join(lines) + "\n"

    all_lines = ["# Wszystkie rekordy", "", "Pełna lista rekordów z `wyniki/*.json`.", "", f"Data: {now}  ", f"SHA-256: `{sha}`  ", ""]
    all_lines.extend(md_table(["measured_by", "model", "benchmark", "metric", "score", "n", "status", "source", "deviations"],
        [[r.get("measured_by"), r.get("model"), r.get("benchmark"), r.get("metric"), fmt_score(r), r.get("n"), r.get("status"), src_link(r), "; ".join(r.get("deviations", [])) or "—"] for r in sorted(records, key=lambda x: (x.get("measured_by", ""), x.get("benchmark", ""), sort_key_model(x.get("model", ""))))]))
    all_lines.append("")
    all_rec = "\n".join(all_lines) + "\n"
    return main, all_rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    main_md, all_md = build()
    if args.check:
        for p, content, name in [(OUT, main_md, "leaderboard.md"), (ALL_REC, all_md, "docs/wszystkie_rekordy.md")]:
            if not p.exists():
                print(f"{name} missing")
                raise SystemExit(1)
            if p.read_text(encoding="utf-8") != content:
                print(f"{name} out of date")
                raise SystemExit(1)
        if not SLAYER_SVG.exists():
            print("docs/slayer_checkpointy.svg missing")
            raise SystemExit(1)
        print("OK: leaderboard files match data")
        return
    OUT.write_text(main_md, encoding="utf-8")
    ALL_REC.write_text(all_md, encoding="utf-8")
    print("written", OUT, ALL_REC, SLAYER_SVG)


if __name__ == "__main__":
    main()
