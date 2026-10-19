"""Build a dependency-free GitHub Pages explorer of precomputed measured results."""
from pathlib import Path
import csv
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build():
    dest = ROOT/'site'
    dest.mkdir(exist_ok=True)
    summary = json.loads((ROOT/'reports/summary.json').read_text())
    with (ROOT/'reports/development_study.csv').open(newline='', encoding='utf-8') as source:
        scenarios = list(csv.DictReader(source))
    for row in scenarios:
        for key in list(row):
            if key == 'scenario':
                continue
            if key == 'within_exploratory_margin':
                row[key] = row[key].lower() == 'true'
            else:
                row[key] = float(row[key])
    template = (ROOT/'web/index.html').read_text(encoding='utf-8')
    payload = json.dumps({'benchmark': summary, 'scenarios': scenarios}, separators=(',', ':')).replace('</', '<\\/')
    (dest/'index.html').write_text(template.replace('/*__DATA__*/', payload), encoding='utf-8')
    (dest/'.nojekyll').touch()
    for name in ['summary.json','development_study.csv','requirements_traceability.csv','selected_cycles.csv']:
        shutil.copy2(ROOT/'reports'/name, dest/name)
    print(f'Built {len(scenarios)} measured scenarios and four downloadable audit files.')


if __name__ == '__main__':
    build()
