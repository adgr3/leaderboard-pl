import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WYNIKI = ROOT / "wyniki"
OUT = ROOT / "leaderboard.md"
DOCS = ROOT / "docs"
WYKRESY = DOCS / "wykresy"
ALL_REC = DOCS / "wszystkie_rekordy.md"
SLAYER_SVG = WYKRESY / "slayer_checkpointy.svg"
HEATMAP_SVG = WYKRESY / "ranking_heatmapa.svg"
AVG_SVG = WYKRESY / "ranking_srednia.svg"
TOKEN_SVG = WYKRESY / "tokenizery_fertility.svg"
ALIASES = ROOT / "schema" / "aliasy.json"
OPISY = ROOT / "opisy" / "benchmarki.yaml"

LM_EVAL_15 = [
    "arc-challenge", "arc-easy", "blimp", "ewok", "hellaswag", "lambada", "mathqa",
    "medmcqa", "multiblimp-pl", "piqa", "pubmedqa", "social-iqa", "wikitext-2", "winogrande", "wsc273",
]

PERCENT_METRICS = {
    "acc", "acc_norm", "accuracy", "pass_rate", "prompt_level_strict_acc",
    "prompt_level_loose_acc", "instruction_level_strict_acc", "instruction_level_loose_acc",
    "prompt_level_strict", "prompt_level_loose", "instruction_level_strict", "instruction_level_loose",
    "overall_acc", "exact_match (flexible-extract)", "ewok",
}
PERCENT_BENCH_HINTS = ("ifeval", "ifbench", "ifstruct", "multi-if", "bfcl", "automationbench", "aa-omniscience", "aa-lcr", "ruler", "hle", "terminal-bench", "humanity")
LOWER_BETTER_METRICS = {"byte_perplexity", "fertility (tokens/word)", "bytes per token"}
LOWER_BETTER_BENCH = {"wikitext-2"}

FAMILY_ORDER = ["polish_instructions","knowledge_reasoning","code","long_context","agents_tools","language_modeling","tokenizers"]
FAMILY_TITLES = {
    "polish_instructions": ("Polszczyzna i instrukcje", "Polish and instructions"),
    "knowledge_reasoning": ("Wiedza i rozumowanie", "Knowledge and reasoning"),
    "code": ("Kod", "Code"),
    "long_context": ("Długi kontekst", "Long context"),
    "agents_tools": ("Agenci i narzędzia", "Agents and tools"),
    "language_modeling": ("Modelowanie języka", "Language modeling"),
    "tokenizers": ("Tokenizery", "Tokenizers"),
}


def load_aliases():
    if ALIASES.exists():
        return json.loads(ALIASES.read_text(encoding="utf-8")).get("aliases", {})
    return {}

ALIASES_MAP = load_aliases()


def load_opisy():
    try:
        import yaml
    except Exception:
        return {}
    if not OPISY.exists():
        return {}
    data = yaml.safe_load(OPISY.read_text(encoding="utf-8")) or {}
    return data


OPISY_MAP = load_opisy()


def norm_bench(name):
    return ALIASES_MAP.get(name, name)


def data_sha():
    h = hashlib.sha256()
    for p in sorted(WYNIKI.glob("*.json"), key=lambda p: p.name):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def load_records():
    recs = []
    for p in sorted(WYNIKI.glob("*.json"), key=lambda p: p.name):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["benchmark"] = norm_bench(d.get("benchmark"))
        d["_file"] = p.name
        recs.append(d)
    recs.sort(key=lambda r: (r.get("benchmark",""), sort_key_model(r.get("model","")), r.get("metric",""), r.get("measured_by",""), r.get("_file","")))
    return recs


def is_percent(r):
    m = (r.get("metric") or "").lower()
    b = (r.get("benchmark") or "").lower()
    if m in LOWER_BETTER_METRICS or "byte_perplexity" in m or "perplexity" in m or "bytes per token" in m or "fertility" in m:
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


def direction_for(r):
    b = r.get("benchmark")
    o = OPISY_MAP.get(b, {})
    d = o.get("direction")
    if d in ("higher", "lower"):
        return d
    m = (r.get("metric") or "").lower()
    if m in LOWER_BETTER_METRICS or b in LOWER_BETTER_BENCH or "perplexity" in m or "fertility" in m or "bytes per token" in m:
        return "lower"
    return "higher"


def score_value(r):
    s = r.get("score")
    if s is None:
        return None
    pct = is_percent(r)
    if pct and 0 <= s <= 1.5:
        return s * 100
    return float(s)


def fmt_num(v, pct=False):
    if v is None:
        return "—"
    if pct:
        return f"{v:.1f}%"
    if abs(v) >= 100 or float(v).is_integer():
        if abs(v) < 10000 and float(v).is_integer():
            return str(int(v))
        return f"{v:.4g}"
    return f"{v:.4f}".rstrip("0").rstrip(".")


def fmt_score(r):
    if r.get("status") == "null" or r.get("score") is None:
        reason = r.get("null_reason") or "brak powodu"
        reason = str(reason).replace("|", "/").replace("\n", " ")
        low = reason.lower()
        if "not run" in low:
            idx = low.find("not run")
            rest = reason[idx + len("not run"):].strip(" -—:()")
            if rest:
                return f"not run ({rest})"
            return "not run"
        return f"null ({reason})"
    v = score_value(r)
    pct = is_percent(r)
    base = fmt_num(v, pct=pct)
    se = r.get("stderr")
    ci = r.get("ci95")
    b = (r.get("benchmark") or "").lower()
    metric = (r.get("metric") or "").lower()
    if "token" in b or "fertility" in metric or "bytes per token" in metric:
        return base
    if se is not None and se != 0:
        se_v = se * 100 if pct and 0 <= se <= 1.5 else se
        return f"{base} ± {fmt_num(se_v, pct=pct)}" if pct else f"{base} ± {fmt_num(se_v)}"
    if ci:
        return base
    return base


def src_link(r):
    s = r.get("source", {})
    url = s.get("url")
    path = s.get("path", "")
    label = path.split("/")[-1] if path else "źródło"
    if url and isinstance(url, str) and url.startswith("http"):
        return f"[{label}]({url})"
    if url and isinstance(url, str) and url.startswith("local://"):
        return f"{label} (lokalnie)"
    if url:
        return f"[{label}]({url})"
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
    ml = (m or "").lower()
    if ml.startswith("slayer"):
        return (0, ml)
    if ml.startswith("bielik"):
        return (1, ml)
    if ml.startswith("lfm"):
        return (2, ml)
    if ml.startswith("qwen"):
        return (3, ml)
    return (9, ml)


def family_group(model):
    m = (model or "").lower()
    if m.startswith("slayer"):
        return "Slayer"
    if m.startswith("bielik"):
        return "Bielik"
    if m.startswith("lfm"):
        return "LFM"
    if m.startswith("qwen"):
        return "Qwen"
    return "Inne"


def is_tokenizer_record(r):
    b = (r.get("benchmark") or "").lower()
    m = (r.get("metric") or "").lower()
    o = OPISY_MAP.get(r.get("benchmark"), {})
    return o.get("family") == "tokenizers" or "token fertility" in b or "bytes per token" in b or "fertility" in m


def benchmark_family(r):
    b = r.get("benchmark")
    o = OPISY_MAP.get(b, {})
    fam = o.get("family")
    if fam:
        return fam
    if is_tokenizer_record(r):
        return "tokenizers"
    bl = (b or "").lower()
    if any(k in bl for k in ("scicode", "livecode", "code")):
        return "code"
    if any(k in bl for k in ("ruler", "aa-lcr", "long")):
        return "long_context"
    if any(k in bl for k in ("bfcl", "terminal-bench", "automationbench", "tool", "omniscience")):
        return "agents_tools"
    if any(k in bl for k in ("multiblimp", "if", "ifeval", "ifbench", "multi-if", "ifstruct")):
        return "polish_instructions"
    if any(k in bl for k in ("wikitext", "lambada", "blimp")):
        return "language_modeling"
    return "knowledge_reasoning"


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        cells = []
        for c in row:
            if c is None:
                cells.append("—")
            else:
                cells.append(str(c).replace("\n", " ").replace("|", "/"))
        out.append("| " + " | ".join(cells) + " |")
    return out


def bench_display(b):
    o = OPISY_MAP.get(b, {})
    return o.get("display_pl") or b


def is_comparable(r):
    if r.get("status") != "measured":
        return False
    if r.get("deviations"):
        return False
    comp = r.get("comparable_to_reference")
    if isinstance(comp, dict) and comp.get("comparable") is False:
        return False
    return True


def pick_primary(records, benchmark, model):
    rs = [r for r in records if r.get("benchmark") == benchmark and r.get("model") == model and r.get("status") in ("measured","null")]
    if not rs:
        return None
    # prefer comparable measured, then measured, then null; stable by file
    rs.sort(key=lambda r: (0 if is_comparable(r) else 1 if r.get("status") == "measured" else 2, r.get("_file","")))
    return rs[0]


def svg_escape(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')


def short_model(m):
    m = m.replace("SlayerLab/","").replace("speakleash/","")
    if len(m) > 28:
        return m[:25] + "…"
    return m


def svg_header(w,h,title,subtitle=None):
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Arial, sans-serif">']
    lines.append('<rect width="100%" height="100%" fill="white"/>')
    lines.append(f'<text x="20" y="28" font-size="16" font-weight="bold" fill="#111">{svg_escape(title)}</text>')
    if subtitle:
        lines.append(f'<text x="20" y="46" font-size="11" fill="#444">{svg_escape(subtitle)}</text>')
    return lines


WRITE_SVG = True
SVG_WRITTEN = {}


def write_svg(path, lines):
    content = "\n".join(lines) + "\n"
    SVG_WRITTEN[str(path.relative_to(ROOT)).replace("\\", "/")] = content
    if WRITE_SVG:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

def build_bar_svg(path, title, subtitle, items, value_label, lower_better=False):
    # items: [(label, value, se, note, color)]
    if not items:
        write_svg(path, svg_header(640,80,title,subtitle)+['<text x="20" y="70" font-size="12">Brak danych.</text>','</svg>'])
        return
    max_label = max(len(i[0]) for i in items)
    left = min(280, max(160, max_label*6 + 20))
    W = 920
    top = 64
    row_h = 24
    H = top + row_h*len(items) + 50
    vals = [i[1] for i in items if i[1] is not None]
    vmax = max(vals) if vals else 1.0
    vmin = 0.0
    if lower_better:
        # show absolute values, smaller bar is better; axis from 0 to vmax
        pass
    span = (vmax - vmin) or 1.0
    plot_w = W - left - 140
    lines = svg_header(W,H,title,subtitle)
    lines.append(f'<line x1="{left}" y1="{top-10}" x2="{left}" y2="{H-35}" stroke="#555"/>')
    for t in range(5):
        x = left + plot_w*t/4
        val = vmin + span*t/4
        lines.append(f'<line x1="{x:.1f}" y1="{top-10}" x2="{x:.1f}" y2="{H-35}" stroke="#ddd"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-18}" font-size="10" text-anchor="middle" fill="#444">{svg_escape(fmt_num(val, pct=("%" in value_label)))}</text>')
    lines.append(f'<text x="{left + plot_w/2:.1f}" y="{H-4}" font-size="11" text-anchor="middle" fill="#444">{svg_escape(value_label)}</text>')
    for idx,(label,val,se,note,color) in enumerate(items):
        y = top + idx*row_h
        lines.append(f'<text x="16" y="{y+15}" font-size="11" fill="#111">{svg_escape(label)}</text>')
        if val is None:
            lines.append(f'<text x="{left+6}" y="{y+15}" font-size="11" fill="#666">brak</text>')
            continue
        bw = (val - vmin)/span*plot_w
        bw = max(0, min(plot_w, bw))
        lines.append(f'<rect x="{left}" y="{y+3}" width="{bw:.2f}" height="14" fill="{color}" opacity="0.85"/>')
        if se is not None and se != 0:
            se_v = se
            err = se_v/span*plot_w
            cx = left + bw
            lines.append(f'<line x1="{cx-err:.2f}" y1="{y+10}" x2="{cx+err:.2f}" y2="{y+10}" stroke="#222"/>')
            lines.append(f'<line x1="{cx-err:.2f}" y1="{y+6}" x2="{cx-err:.2f}" y2="{y+14}" stroke="#222"/>')
            lines.append(f'<line x1="{cx+err:.2f}" y1="{y+6}" x2="{cx+err:.2f}" y2="{y+14}" stroke="#222"/>')
        txt = fmt_num(val, pct=("%" in value_label))
        if note:
            txt += f" {note}"
        lines.append(f'<text x="{left+bw+6:.2f}" y="{y+15}" font-size="10" fill="#111">{svg_escape(txt)}</text>')
    lines.append('</svg>')
    write_svg(path, lines)


def build_heatmap_svg(path, models, benchmarks, matrix, title, subtitle):
    # matrix[model][bench] = normalized 0..1 or None; display value separate
    if not models or not benchmarks:
        write_svg(path, svg_header(640,80,title,subtitle)+['<text x="20" y="70" font-size="12">Brak danych.</text>','</svg>'])
        return
    cell_w, cell_h = 54, 22
    left, top = 220, 90
    W = left + cell_w*len(benchmarks) + 40
    H = top + cell_h*len(models) + 70
    lines = svg_header(W,H,title,subtitle)
    for j,b in enumerate(benchmarks):
        x = left + j*cell_w + cell_w/2
        lines.append(f'<text x="{x:.1f}" y="{top-18}" font-size="9" text-anchor="middle" fill="#111">{svg_escape(b)}</text>')
    for i,m in enumerate(models):
        y = top + i*cell_h
        lines.append(f'<text x="{left-8}" y="{y+15}" font-size="10" text-anchor="end" fill="#111">{svg_escape(short_model(m))}</text>')
        for j,b in enumerate(benchmarks):
            x = left + j*cell_w
            cell = matrix.get(m,{}).get(b)
            if cell is None:
                color = "#f3f3f3"; txt = "—"; tcolor="#777"
            else:
                norm, disp, best = cell
                # green scale
                g = int(230 - 140*norm)
                r = int(245 - 80*norm)
                bl = int(245 - 140*norm)
                color = f"rgb({r},{g},{bl})"
                txt = disp
                tcolor = "#111" if norm < 0.75 else "#fff"
            stroke = "#2b6cb0" if cell and cell[2] else "#ffffff"
            sw = 1.5 if cell and cell[2] else 0.5
            lines.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{color}" stroke="{stroke}" stroke-width="{sw}"/>')
            lines.append(f'<text x="{x+cell_w/2:.1f}" y="{y+14}" font-size="8.5" text-anchor="middle" fill="{tcolor}">{svg_escape(txt)}</text>')
    # legend
    ly = H - 28
    for k in range(6):
        norm=k/5
        g=int(230-140*norm); r=int(245-80*norm); bl=int(245-140*norm)
        x=left + k*30
        lines.append(f'<rect x="{x}" y="{ly}" width="30" height="10" fill="rgb({r},{g},{bl})" stroke="#ccc"/>')
    lines.append(f'<text x="{left}" y="{ly-4}" font-size="10" fill="#444">gorzej</text>')
    lines.append(f'<text x="{left+150}" y="{ly-4}" font-size="10" fill="#444">lepiej (w kolumnie)</text>')
    lines.append('</svg>')
    write_svg(path, lines)


def build_slayer_svg(records, path=SLAYER_SVG):
    slayer = [r for r in records if (r.get("model") or "").lower().startswith("slayer") and r.get("status") == "measured" and not is_tokenizer_record(r)]
    by_bench = defaultdict(list)
    for r in slayer:
        by_bench[r["benchmark"]].append(r)
    benchs = [b for b, rs in by_bench.items() if len({x["model"] for x in rs}) >= 2]
    benchs = sorted(benchs, key=lambda b: (-len({x["model"] for x in by_bench[b]}), b))[:8]
    if not benchs:
        write_svg(path, svg_header(640,80,"Slayer – checkpointy")+['<text x="20" y="70" font-size="12">Brak danych checkpointów.</text>','</svg>'])
        return
    models = sorted({r["model"] for r in slayer if r["benchmark"] in benchs}, key=lambda m: sort_key_model(m))
    colors = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b","#e377c2","#17becf"]
    W,H = 980, 420
    pad_l,pad_r,pad_t,pad_b = 70, 260, 70, 70
    plot_w = W-pad_l-pad_r
    plot_h = H-pad_t-pad_b
    lines = svg_header(W,H,"Slayer – postęp po checkpointach","Wartości znormalizowane per benchmark w obrębie widocznych checkpointów; oś Y: 0=najgorszy, 1=najlepszy.")
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#333"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#333"/>')
    for t in range(5):
        y = pad_t + plot_h*(1-t/4)
        val=t/4
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#eee"/>')
        lines.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" font-size="10" text-anchor="end" fill="#444">{val:.2f}</text>')
    lines.append(f'<text x="18" y="{pad_t+plot_h/2:.1f}" font-size="11" transform="rotate(-90 18,{pad_t+plot_h/2:.1f})" fill="#444">wynik znormalizowany</text>')
    for i,m in enumerate(models):
        x = pad_l + (i/(max(1,len(models)-1)))*plot_w
        lines.append(f'<text x="{x:.1f}" y="{H-28}" font-size="10" text-anchor="middle" fill="#111">{svg_escape(m.replace("SlayerLab/","").replace("slayer","s"))}</text>')
        lines.append(f'<line x1="{x:.1f}" y1="{pad_t+plot_h}" x2="{x:.1f}" y2="{pad_t+plot_h+4}" stroke="#333"/>')
    lines.append(f'<text x="{pad_l+plot_w/2:.1f}" y="{H-8}" font-size="11" text-anchor="middle" fill="#444">checkpoint / model</text>')
    for bi,b in enumerate(benchs):
        color=colors[bi%len(colors)]
        pts=[]
        vals=[]
        for m in models:
            rs=[r for r in by_bench[b] if r["model"]==m and r.get("score") is not None]
            if not rs: continue
            r=rs[0]
            v=score_value(r)
            vals.append((m,v,r))
        if not vals: continue
        raw=[v for _,v,_ in vals]
        vmin,vmax=min(raw),max(raw)
        span=(vmax-vmin) or 1.0
        dirn=direction_for(vals[0][2])
        for m,v,r in vals:
            norm=(v-vmin)/span
            if dirn=='lower': norm=1-norm
            x = pad_l + (models.index(m)/(max(1,len(models)-1)))*plot_w
            y = pad_t + (1-norm)*plot_h
            pts.append((x,y,norm,v))
        if len(pts)>=2:
            d="M "+" L ".join(f"{x:.1f},{y:.1f}" for x,y,_,_ in pts)
            lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        for x,y,norm,v in pts:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"><title>{svg_escape(b)}: {fmt_num(v)}</title></circle>')
        ly=86+bi*18
        lines.append(f'<rect x="{W-pad_r+10}" y="{ly-10}" width="12" height="12" fill="{color}"/>')
        label=bench_display(b)
        label=label[:34]+("…" if len(label)>34 else "")
        lines.append(f'<text x="{W-pad_r+28}" y="{ly}" font-size="10.5" fill="#111">{svg_escape(label)}</text>')
    lines.append('</svg>')
    write_svg(path, lines)


def compute_main_ranking(records):
    # 15 lm-eval benchmarks, all authors, comparable settings only
    rows=[]
    for r in records:
        if r.get('benchmark') not in LM_EVAL_15: continue
        if not is_comparable(r): continue
        rows.append(r)
    # pick one per model/benchmark: prefer adgr3? no, include all authors but comparable; prefer measured and stable
    by_mb=defaultdict(list)
    for r in rows:
        by_mb[(r['model'],r['benchmark'])].append(r)
    chosen={}
    for k,rs in by_mb.items():
        rs.sort(key=lambda r:(0 if r.get('measured_by')=='adgr3' else 1, r.get('_file','')))
        chosen[k]=rs[0]
    models=sorted({m for m,_ in chosen.keys()}, key=sort_key_model)
    benchmarks=list(LM_EVAL_15)
    # averages only when complete over 15
    averages={}
    for m in models:
        vals=[]
        complete=True
        for b in benchmarks:
            r=chosen.get((m,b))
            if not r or r.get('score') is None:
                complete=False; break
            v=score_value(r)
            dirn=direction_for(r)
            norm = v
            # normalize per benchmark later; here keep raw
            vals.append((b,v,dirn))
        if complete:
            averages[m]=vals
    # normalized means
    norm_means={}
    if averages:
        for b in benchmarks:
            col=[]
            for m in models:
                r=chosen.get((m,b))
                if r and r.get('score') is not None and is_comparable(r):
                    col.append(score_value(r))
            if not col: continue
            vmin,vmax=min(col),max(col)
            span=(vmax-vmin) or 1.0
            dirn=direction_for(chosen[next((m,b) for m in models if chosen.get((m,b)))])
            for m in models:
                r=chosen.get((m,b))
                if not r or r.get('score') is None or not is_comparable(r): continue
                v=score_value(r)
                nv=(v-vmin)/span
                if dirn=='lower': nv=1-nv
                norm_means.setdefault(m,[]).append(nv)
    mean_score={m:(sum(v)/len(v)*100) for m,v in norm_means.items() if len(v)==len(benchmarks)}
    # sort models by mean desc, then name
    models_sorted=sorted(models, key=lambda m:(0 if m in mean_score else 1, -(mean_score.get(m,-1)), sort_key_model(m)))
    return models_sorted, benchmarks, chosen, mean_score


def build_ranking_charts(models, benchmarks, chosen, mean_score):
    # heatmap normalized by column
    matrix={}
    for m in models:
        matrix[m]={}
        for b in benchmarks:
            r=chosen.get((m,b))
            if not r or r.get('score') is None: 
                matrix[m][b]=None
                continue
            # compute norm
            col=[score_value(chosen[(mm,b)]) for mm in models if chosen.get((mm,b)) and chosen[(mm,b)].get('score') is not None]
            vmin,vmax=min(col),max(col)
            span=(vmax-vmin) or 1.0
            v=score_value(r)
            nv=(v-vmin)/span
            dirn=direction_for(r)
            if dirn=='lower': nv=1-nv
            disp = fmt_num(v, pct=is_percent(r))
            # best?
            best=False
            if dirn=='higher':
                best = v==vmax
            else:
                best = v==vmin
            matrix[m][b]=(nv, disp, best)
    disp_b=[bench_display(b).replace(' (eksploracyjny, CoT zero-shot)','')[:10] for b in benchmarks]
    build_heatmap_svg(HEATMAP_SVG, models, benchmarks, matrix,
                      "Ranking główny – heatmapa (15 benchmarków lm-eval)",
                      "Kolor = wynik znormalizowany w kolumnie; obwódka = najlepszy wynik w kolumnie.")
    # but heatmap uses benchmark keys as headers; better short labels
    # rebuild with short labels by mapping
    matrix2={}
    for m in models:
        matrix2[m]={}
        for b,db in zip(benchmarks,disp_b):
            matrix2[m][db]=matrix[m][b]
    build_heatmap_svg(HEATMAP_SVG, models, disp_b, matrix2,
                      "Ranking główny – heatmapa (15 benchmarków lm-eval)",
                      "Kolor = wynik znormalizowany w kolumnie; obwódka = najlepszy wynik w kolumnie.")

    items=[]
    for m in models:
        if m in mean_score:
            items.append((short_model(m), mean_score[m], None, '★' if any(chosen.get((m,b),{}).get('measured_by')=='adgr3' for b in benchmarks) else '', '#4c78a8'))
        else:
            items.append((short_model(m), None, None, 'niekompletny', '#999999'))
    build_bar_svg(AVG_SVG, "Ranking główny – średnia znormalizowana", "Średnia po 15 benchmarkach lm-eval; tylko modele z kompletem porównywalnych wyników.", items, "średnia (0–100, wyżej lepiej)")


def render_main_ranking(models, benchmarks, chosen, mean_score):
    lines=[]
    lines.append("## Ranking główny (15 benchmarków lm-eval)")
    lines.append("")
    lines.append("Tabela obejmuje wszystkie modele z porównywalnymi wynikami na 15 benchmarkach lm-eval (wszyscy autorzy; wiersze z odstępstwem † i nieporównywalne są poza rankingiem/średnią). Średnia to średnia wyników znormalizowanych w kolumnie (0–100), liczona tylko przy komplecie 15/15. ★ = nasz pomiar, † = odstępstwo, ∅ = null.")
    lines.append("")
    headers=["Model","Średnia"] + [bench_display(b) for b in benchmarks]
    rows=[]
    for m in models:
        row=[f"**{m}**" if m in mean_score else m, f"{mean_score[m]:.1f}" if m in mean_score else "—"]
        for b in benchmarks:
            r=chosen.get((m,b))
            if not r:
                row.append("—")
            else:
                row.append(f"{fmt_score(r)} {flag(r)}".strip())
        rows.append(row)
    lines.extend(md_table(headers, rows))
    lines.append("")
    lines.append(f"![Heatmapa rankingu](docs/wykresy/{HEATMAP_SVG.name})")
    lines.append("")
    lines.append(f"![Średnia rankingu](docs/wykresy/{AVG_SVG.name})")
    lines.append("")
    return lines


def family_records(records, fam):
    return [r for r in records if benchmark_family(r)==fam]


def render_family_section(records, fam):
    title_pl,title_en = FAMILY_TITLES[fam]
    rs = family_records(records, fam)
    lines=[f"## {title_pl} / {title_en}", ""]
    o_by_b={}
    for r in rs:
        b=r['benchmark']
        o_by_b.setdefault(b, OPISY_MAP.get(b,{}))
    # family intro
    if fam=="polish_instructions":
        lines.append("Wyróżnik projektu: benchmarki polskie i instrukcyjne (PL/IF). Porównuj wyniki tylko w obrębie tego samego benchmarku, metryki i ustawień; † oznacza odstępstwo.")
    else:
        lines.append(f"Sekcja obejmuje benchmarki z rodziny „{title_pl}”. Porównuj tylko w obrębie tego samego benchmarku, metryki i ustawień.")
    lines.append("")
    # benchmark descriptions
    for b in sorted(o_by_b.keys(), key=lambda x: bench_display(x).lower()):
        o=o_by_b[b]
        lines.append(f"### {bench_display(b)}")
        meas=o.get('measures_pl','')
        meas_en=o.get('measures_en','')
        src=o.get('source_url','')
        meta=f"Język: {o.get('language','?')} · Metryka: `{o.get('metric','?')}` ({'↑ wyżej lepiej' if o.get('direction')=='higher' else '↓ niżej lepiej'}) · n={o.get('n_items','?')}"
        lines.append(f"{meas}")
        lines.append(f"_{meas_en}_  ")
        lines.append(f"{meta}  ")
        if src:
            lines.append(f"Źródło: [{src}]({src})")
        lines.append("")
        # table
        brs=[r for r in rs if r['benchmark']==b]
        # group by metric
        metrics=sorted({r.get('metric') for r in brs})
        for metric in metrics:
            mrs=[r for r in brs if r.get('metric')==metric]
            mrs.sort(key=lambda r:(0 if r.get('status')=='measured' else 1, -(score_value(r) or -1e18) if direction_for(r)=='higher' else (score_value(r) or 1e18), sort_key_model(r.get('model','')), r.get('_file','')))
            rows=[]
            for r in mrs:
                dev = "; ".join(r.get("deviations", [])) or "—"
                set_short = r.get("settings", {}).get("variant") or r.get("subset") or "—"
                rows.append([r.get("model"), metric, fmt_score(r), r.get("n"), flag(r), set_short, src_link(r), dev])
            lines.extend(md_table(["Model","Metryka","Wynik","n","Flagi","Ustawienia","Źródło","Odstępstwa"], rows))
            lines.append("")
            # chart if >=3 measured comparable models
            chart_rs=[r for r in mrs if r.get('status')=='measured' and r.get('score') is not None]
            # unique by model, prefer comparable
            bym={}
            for r in chart_rs:
                k=r['model']
                if k not in bym or (is_comparable(r) and not is_comparable(bym[k])):
                    bym[k]=r
            chart_list=list(bym.values())
            if len(chart_list)>=3:
                dirn=direction_for(chart_list[0])
                chart_list.sort(key=lambda r: score_value(r) if dirn=='higher' else -score_value(r), reverse=(dirn=='higher'))
                items=[]
                for r in chart_list:
                    v=score_value(r)
                    se=r.get('stderr')
                    if se is not None and is_percent(r) and 0 <= se <= 1.5:
                        se=se*100
                    note=flag(r)
                    color='#4c78a8' if r.get('measured_by')=='adgr3' else '#72b7b2'
                    items.append((short_model(r['model']), v, se, note, color))
                safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in f"{b}__{metric}")
                p = WYKRESY / f"{safe[:120]}.svg"
                unit = '%' if is_percent(chart_list[0]) else metric
                build_bar_svg(p, f"{bench_display(b)} – {metric}", f"{'↑ wyżej lepiej' if dirn=='higher' else '↓ niżej lepiej'}; wąsy = SE gdy dostępne; ★=adgr3, †=odstępstwo", items, unit, lower_better=(dirn=='lower'))
                lines.append(f"![{bench_display(b)} {metric}](docs/wykresy/{p.name})")
                lines.append("")
    return lines


def render_polish_section(records):
    # Explicit Polish section per spec
    pl_bench = ["multiblimp-pl","IFBench (Bielik IF-PL local)","IFEval (Bielik IF-PL local)","Token fertility (tokens per word, 7 Polish domains)","Held-out corpus (bytes per token)"]
    lines=["## Polszczyzna / Polish", ""]
    lines.append("To wyróżnik projektu: wyniki na polskich danych i polskojęzycznych/PL-lokalnych benchmarkach. Porównuj tylko w obrębie tego samego benchmarku, metryki i ustawień.")
    lines.append("")
    for b in pl_bench:
        rs=[r for r in records if r.get('benchmark')==b]
        if not rs: 
            continue
        o=OPISY_MAP.get(b,{})
        lines.append(f"### {bench_display(b)}")
        lines.append(o.get('measures_pl',''))
        lines.append(f"_{o.get('measures_en','')}_  ")
        lines.append(f"Język: {o.get('language','?')} · Metryka: `{o.get('metric','?')}` ({'↑' if o.get('direction')=='higher' else '↓'}) · n={o.get('n_items','?')}  ")
        lines.append(f"Źródło: [{o.get('source_url','')}]({o.get('source_url','')})")
        lines.append("")
        metrics=sorted({r.get('metric') for r in rs})
        for metric in metrics:
            mrs=[r for r in rs if r.get('metric')==metric]
            mrs.sort(key=lambda r:(0 if r.get('status')=='measured' else 1, score_value(r) if direction_for(r)=='lower' else -(score_value(r) or -1e18), sort_key_model(r.get('model',''))))
            rows=[]
            for r in mrs:
                rows.append([r.get('model'), metric, fmt_score(r), r.get('n'), flag(r), src_link(r)])
            lines.extend(md_table(["Model","Metryka","Wynik","n","Flagi","Źródło"], rows))
            lines.append("")
    return lines


def render_tokenizers(records):
    toks=[r for r in records if benchmark_family(r)=='tokenizers']
    lines=["## Tokenizery / Tokenizers",""]
    lines.append("Porównania tokenizatorów: fertility (↓ lepiej) i bytes/token (↑ lepiej). Osobna tabela, bez mieszania z benchmarkami modeli.")
    lines.append("")
    for b in sorted({r['benchmark'] for r in toks}, key=lambda x: bench_display(x)):
        o=OPISY_MAP.get(b,{})
        rs=[r for r in toks if r['benchmark']==b and r.get('status')=='measured']
        rs.sort(key=lambda r: score_value(r) if direction_for(r)=='lower' else -(score_value(r) or 0))
        lines.append(f"### {bench_display(b)}")
        lines.append(f"{o.get('measures_pl','')}  ")
        lines.append(f"Źródło: [{o.get('source_url','')}]({o.get('source_url','')})")
        lines.append("")
        rows=[[r.get('model'), r.get('metric'), fmt_score(r), r.get('n'), flag(r), src_link(r)] for r in rs]
        lines.extend(md_table(["Tokenizer/model","Metryka","Wynik","n","Flagi","Źródło"], rows))
        lines.append("")
        if len(rs)>=3:
            dirn=direction_for(rs[0])
            items=[]
            for r in rs:
                v=score_value(r)
                color='#4c78a8' if r.get('measured_by')=='adgr3' else '#72b7b2'
                items.append((short_model(r['model']), v, r.get('stderr'), flag(r), color))
            unit = '%' if is_percent(rs[0]) else rs[0].get('metric')
            build_bar_svg(TOKEN_SVG if b=="Token fertility (tokens per word, 7 Polish domains)" else WYKRESY/f"{(''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in b))[:100]}.svg",
                          f"{bench_display(b)}", f"{'↓ niżej lepiej' if dirn=='lower' else '↑ wyżej lepiej'}", items, unit, lower_better=(dirn=='lower'))
            chart_name = TOKEN_SVG.name if b=="Token fertility (tokens per word, 7 Polish domains)" else f"{(''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in b))[:100]}.svg"
            lines.append(f"![{bench_display(b)}](docs/wykresy/{chart_name})")
            lines.append("")
    return lines


def build():
    records = load_records()
    DOCS.mkdir(parents=True, exist_ok=True)
    WYKRESY.mkdir(parents=True, exist_ok=True)
    now = max(str(r.get("date")) for r in records if r.get("date")) if records else "-"
    sha = data_sha()
    by_mb = Counter(r.get("measured_by") for r in records)
    by_status = Counter(r.get("status") for r in records)
    models = sorted({r.get("model") for r in records})
    benchmarks = sorted({r.get("benchmark") for r in records})
    n_scores = sum(1 for r in records if r.get("status")=="measured" and r.get("score") is not None)

    models_main, benches_main, chosen_main, mean_score = compute_main_ranking(records)
    build_ranking_charts(models_main, benches_main, chosen_main, mean_score)
    build_slayer_svg(records, SLAYER_SVG)
    render_tokenizers(records)  # ensure token chart generated

    lines=[]
    lines.append("# Leaderboard PL")
    lines.append("")
    lines.append("> **PL:** Publiczny, generowany leaderboard wyników benchmarków modeli.  ")
    lines.append("> **EN:** Public, generated leaderboard of model benchmark results.")
    lines.append("")
    lines.append(f"Modele: **{len(models)}** · Benchmarki: **{len(benchmarks)}** · Rekordy: **{len(records)}** (measured: {by_status.get('measured',0)}, null: {by_status.get('null',0)}) · Wyniki liczbowe: **{n_scores}**  ")
    lines.append(f"Najnowszy rekord: **{now}** · Dane SHA-256: `{sha}`")
    lines.append("")
    lines.append("Linki: [Hugging Face Space](https://huggingface.co/spaces/adegier/leaderboard-pl) · [Hugging Face Dataset](https://huggingface.co/datasets/adegier/leaderboard-pl-results) · [Metodologia](METODOLOGIA.md) · [Pełne rekordy](docs/wszystkie_rekordy.md)")
    lines.append("")
    lines.append("## Jak czytać / How to read")
    lines.append("")
    lines.append("- `★` pomiar tego projektu (`adgr3`), `†` odstępstwo/protokół nieporównywalny, `∅` null z powodem, `ⓡ` karta modelu.")
    lines.append("- Porównuj tylko ten sam benchmark, metrykę i porównywalne ustawienia. Wiersze z `†` nie wchodzą do rankingów/średnich.")
    lines.append("- `—` = brak błędu standardowego/CI w źródle. SE pokazujemy jako `±` gdy jest w danych.")
    lines.append("- Wyniki accuracy/pass są w % gdy metryka tego wymaga; BPB/perplexity/fertility/bytes/token zostają w skali oryginalnej.")
    lines.append("")
    lines.append("## Szybka nawigacja")
    lines.append("")
    lines.append("- [Ranking główny](#ranking-główny-15-benchmarków-lm-eval)")
    lines.append("- [Polszczyzna](#polszczyzna--polish)")
    lines.append("- [Wiedza i rozumowanie](#wiedza-i-rozumowanie--knowledge-and-reasoning)")
    lines.append("- [Kod](#kod--code)")
    lines.append("- [Polszczyzna i instrukcje](#polszczyzna-i-instrukcje--polish-and-instructions)")
    lines.append("- [Długi kontekst](#długi-kontekst--long-context)")
    lines.append("- [Agenci i narzędzia](#agenci-i-narzędzia--agents-and-tools)")
    lines.append("- [Modelowanie języka](#modelowanie-języka--language-modeling)")
    lines.append("- [Slayer checkpointy](#slayer-w-checkpointach--slayer-checkpoints)")
    lines.append("- [Tokenizery](#tokenizery--tokenizers)")
    lines.append("- [Odstępstwa](#odstępstwa-i-znane-problemy--deviations)")
    lines.append("- [Metodologia skrótem](#metodologia-skrótem--methodology-summary)")
    lines.append("")

    lines.extend(render_main_ranking(models_main, benches_main, chosen_main, mean_score))
    lines.extend(render_polish_section(records))

    for fam in FAMILY_ORDER:
        if fam == 'tokenizers':
            continue
        lines.extend(render_family_section(records, fam))

    # Slayer section
    lines.append("## Slayer w checkpointach / Slayer checkpoints")
    lines.append("")
    slayer=[r for r in records if (r.get('model') or '').lower().startswith('slayer') and not is_tokenizer_record(r)]
    if slayer:
        rows=[]
        for r in sorted(slayer, key=lambda x:(sort_key_model(x.get('model','')), x.get('benchmark',''), x.get('metric',''), x.get('_file',''))):
            rows.append([r.get('model'), bench_display(r.get('benchmark')), r.get('metric'), fmt_score(r), r.get('n'), flag(r), src_link(r)])
        lines.extend(md_table(["Model","Benchmark","Metryka","Wynik","n","Flagi","Źródło"], rows))
        lines.append("")
        lines.append(f"![Slayer checkpointy](docs/wykresy/{SLAYER_SVG.name})")
        lines.append("")
    else:
        lines.append("_Brak rekordów Slayer._")
        lines.append("")

    lines.extend(render_tokenizers(records))

    # Deviations
    lines.append("## Odstępstwa i znane problemy / Deviations")
    lines.append("")
    prob=[r for r in records if r.get('deviations') or r.get('status')=='null' or (isinstance(r.get('comparable_to_reference'),dict) and r.get('comparable_to_reference',{}).get('comparable') is False)]
    if prob:
        for r in sorted(prob, key=lambda x:(x.get('measured_by',''), x.get('model',''), x.get('benchmark',''), x.get('_file',''))):
            reasons=list(r.get('deviations',[]))
            if r.get('status')=='null':
                reasons.append(f"null: {r.get('null_reason')}")
            comp=r.get('comparable_to_reference')
            if isinstance(comp,dict) and comp.get('comparable') is False:
                reasons.append(f"not comparable: {comp.get('reason')}")
            reason='; '.join(str(x) for x in reasons if x) or '—'
            lines.append(f"- [{r.get('measured_by')}] {r.get('model')} / {r.get('benchmark')} / {r.get('metric')}: {reason} ({src_link(r)})")
    else:
        lines.append("- brak")
    lines.append("")

    # Methodology short
    lines.append("## Metodologia skrótem / Methodology summary")
    lines.append("")
    lines.append("- Dane pochodzą z `wyniki/*.json`, walidowane schematem `schema/wynik.schema.json`; tabela jest generowana przez `scripts/buduj.py --check`.")
    lines.append("- Opisy benchmarków są w `opisy/benchmarki.yaml` i muszą mieć źródło.")
    lines.append("- Ranking główny: 15 benchmarków lm-eval, tylko porównywalne wyniki, bez `†`; średnia tylko przy komplecie 15/15.")
    lines.append("- Szczegóły: [METODOLOGIA.md](METODOLOGIA.md).")
    lines.append("")

    lines.append("## Jak dodać wynik / How to add a result")
    lines.append("")
    lines.append("1. Dodaj JSON do `wyniki/` zgodny ze schematem i z pełnym `source`.")
    lines.append("2. Ustaw `measured_by`, `status`, `deviations`, `comparable_to_reference` uczciwie.")
    lines.append("3. Uruchom `python scripts/buduj.py` i `python scripts/buduj.py --check`.")
    lines.append("4. Uruchom `python scripts/eksport_hf.py --check` i `python -m pytest -q`.")
    lines.append("")

    lines.append("## Stopka")
    lines.append("")
    lines.append(f"- Najnowszy rekord: {now}")
    lines.append(f"- SHA-256 danych (`wyniki/*.json`): `{sha}`")
    lines.append(f"- Rekordy per measured_by: {dict(sorted(by_mb.items()))} (adgr3: {by_mb.get('adgr3',0)})")
    lines.append(f"- Modele w rankingu głównym (komplet 15/15): {sum(1 for m in models_main if m in mean_score)} / {len(models_main)}")
    lines.append("- Pełna lista: [docs/wszystkie_rekordy.md](docs/wszystkie_rekordy.md)")
    lines.append("")

    main_md = "\n".join(lines) + "\n"

    all_lines=["# Wszystkie rekordy / All records","","Pełna lista rekordów z `wyniki/*.json`.","","Najnowszy rekord: " + now + "  ", f"SHA-256: `{sha}`  ", ""]
    all_lines.extend(md_table(["measured_by","model","benchmark","metric","score","n","status","source","deviations"],
        [[r.get("measured_by"), r.get("model"), r.get("benchmark"), r.get("metric"), fmt_score(r), r.get("n"), r.get("status"), src_link(r), "; ".join(r.get("deviations", [])) or "—"] for r in sorted(records, key=lambda x:(x.get('measured_by',''), x.get('benchmark',''), sort_key_model(x.get('model','')), x.get('_file','')))]))
    all_lines.append("")
    all_rec="\n".join(all_lines)+"\n"
    return main_md, all_rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    global WRITE_SVG
    WRITE_SVG = not args.check
    SVG_WRITTEN.clear()
    main_md, all_md = build()
    expected = {
        OUT: main_md,
        ALL_REC: all_md,
    }
    if args.check:
        for pth, content in expected.items():
            if not pth.exists():
                print(f"{pth.relative_to(ROOT)} missing")
                raise SystemExit(1)
            if pth.read_text(encoding='utf-8') != content:
                print(f"{pth.relative_to(ROOT)} out of date")
                raise SystemExit(1)
        # SVGs must match exactly
        on_disk = {str(p.relative_to(ROOT)).replace("\\","/"): p.read_text(encoding='utf-8') for p in sorted(WYKRESY.glob('*.svg'))}
        if set(on_disk.keys()) != set(SVG_WRITTEN.keys()):
            print("docs/wykresy svg set differs")
            extra = sorted(set(on_disk)-set(SVG_WRITTEN))
            missing = sorted(set(SVG_WRITTEN)-set(on_disk))
            if extra: print(' extra', extra[:10])
            if missing: print(' missing', missing[:10])
            raise SystemExit(1)
        for k in sorted(SVG_WRITTEN):
            if on_disk[k] != SVG_WRITTEN[k]:
                print(f"{k} out of date")
                raise SystemExit(1)
        print("OK: leaderboard files match data")
        return
    OUT.write_text(main_md, encoding='utf-8')
    ALL_REC.write_text(all_md, encoding='utf-8')
    # remove stale svgs
    for pth in WYKRESY.glob('*.svg'):
        rel = str(pth.relative_to(ROOT)).replace("\\","/")
        if rel not in SVG_WRITTEN:
            pth.unlink()
    print("written", OUT, ALL_REC)
    print("svgs", len(SVG_WRITTEN))


if __name__ == "__main__":
    main()
