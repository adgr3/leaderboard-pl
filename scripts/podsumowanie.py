import json,glob
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
recs=[json.load(open(p,encoding='utf-8')) for p in glob.glob(str(ROOT/'wyniki/*.json'))]
models={r['model'] for r in recs}
benches={r['benchmark'] for r in recs}
print('records',len(recs))
print('models',len(models))
print('benchmarks',len(benches))
print('measured',sum(1 for r in recs if r['status']=='measured'))
print('null',sum(1 for r in recs if r['status']=='null'))
print('by_measured',dict(Counter(r['measured_by'] for r in recs)))
