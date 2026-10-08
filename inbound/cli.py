"""Command line: python -m inbound <step> ...

Exit codes: 0 ok, 1 done but lines were held back, 2 refused.
"""
import argparse
import json
import os
import sys

from inbound import stafile
from inbound.stage import StageRefused, build_stage


def summary(stage, paths):
    out = []
    for wf, path in zip(stage["workflows"], paths):
        out.append(f"{wf['name']}: {wf['sku_count']} SKUs, {wf['units']} units -> {path}")
        out.append(f"  after upload the page should read \"{wf['expected_counter']}\"")
    for h in stage["held"]:
        out.append(f"HELD {h['qty']} units of {h['reason']}")
    for f in stage["flags"]:
        out.append(f"NOTE {f}")
    return "\n".join(out)


def cmd_sta_file(a):
    with open(a.input) as f:
        doc = json.load(f)
    try:
        stage = build_stage(doc)
    except StageRefused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    paths = stafile.write_all(stage, a.out_dir)
    with open(os.path.join(a.out_dir, "stage.json"), "w") as f:
        json.dump({**stage, "files": paths}, f, indent=2)
        f.write("\n")
    print(summary(stage, paths))
    return 1 if stage["held"] else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="inbound", description="Instrumentpro invoice to inbound")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sta-file", help="split units into workflows and write upload files")
    s.add_argument("--input", required=True,
                   help='{"vendor", "invoice", "lines": [{"sku", "asin", "fnsku", "qty"}]}')
    s.add_argument("--out-dir", required=True)
    s.set_defaults(fn=cmd_sta_file)

    a = p.parse_args(argv)
    return a.fn(a)
