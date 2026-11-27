import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPISY_PATH = ROOT / "opisy" / "benchmarki.yaml"

REQUIRED = {
    "display_pl", "display_en", "family", "family_pl", "family_en",
    "measures_pl", "measures_en", "language", "metric", "direction",
    "n_items", "source_url", "source_note",
}
FAMILIES = {
    "polish_instructions": ("Polszczyzna i instrukcje", "Polish and instructions"),
    "knowledge_reasoning": ("Wiedza i rozumowanie", "Knowledge and reasoning"),
    "code": ("Kod", "Code"),
    "long_context": ("Długi kontekst", "Long context"),
    "agents_tools": ("Agenci i narzędzia", "Agents and tools"),
    "language_modeling": ("Modelowanie języka", "Language modeling"),
    "tokenizers": ("Tokenizery", "Tokenizers"),
}


def load_opisy(path=OPISY_PATH):
    try:
        import yaml
    except Exception as e:
        raise RuntimeError("PyYAML required for opisy/benchmarki.yaml") from e
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("opisy/benchmarki.yaml must be a mapping")
    return data


def validate_opisy(opisy, benchmark_names):
    errors = []
    names = set(benchmark_names)
    opisy_names = set(opisy.keys())
    for b in sorted(names - opisy_names):
        errors.append(f"missing description for benchmark: {b}")
    for b in sorted(opisy_names - names):
        errors.append(f"orphan description: {b}")
    for b, d in sorted(opisy.items()):
        if not isinstance(d, dict):
            errors.append(f"{b}: not a mapping")
            continue
        missing = REQUIRED - set(d.keys())
        if missing:
            errors.append(f"{b}: missing fields {sorted(missing)}")
        fam = d.get("family")
        if fam not in FAMILIES:
            errors.append(f"{b}: unknown family {fam}")
        if d.get("direction") not in {"higher", "lower"}:
            errors.append(f"{b}: bad direction {d.get('direction')}")
        if not isinstance(d.get("n_items"), int) or d.get("n_items") <= 0:
            errors.append(f"{b}: n_items must be positive int")
        for k in ("display_pl", "display_en", "measures_pl", "measures_en", "language", "metric", "source_url", "source_note"):
            v = d.get(k)
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{b}: {k} must be non-empty string")
    return errors
