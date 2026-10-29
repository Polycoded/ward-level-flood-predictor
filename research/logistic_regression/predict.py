"""Portable inference for an uncalibrated satellite-inundation proxy."""
import argparse
import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def score(model, row):
    values = []
    for i, name in enumerate(model['features']):
        raw = row.get(name)
        value = float(raw) if raw not in (None, '') else model['medians'][i]
        if not math.isfinite(value):
            value = model['medians'][i]
        values.append((value - model['means'][i]) / model['scales'][i])
    z = model['intercept'] + sum(a*b for a, b in zip(values, model['coefficients']))
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', type=Path, default=HERE/'results/model_full_refit.json')
    args = parser.parse_args()
    model = json.loads(args.model.read_text())
    with args.features.open(newline='') as source:
        rows = csv.DictReader(source)
        if not set(model['features']).issubset(rows.fieldnames or []):
            parser.error('Input is missing required feature columns')
        with args.output.open('x', newline='') as dest:
            writer = csv.DictWriter(dest, fieldnames=['ward_id', 'event_id', 'proxy_score', 'proxy_flag_at_0_5'])
            writer.writeheader()
            for row in rows:
                p = score(model, row)
                writer.writerow(dict(ward_id=row.get('ward_id', ''), event_id=row.get('event_id', ''), proxy_score=p,
                                     proxy_flag_at_0_5=int(p >= .5)))
