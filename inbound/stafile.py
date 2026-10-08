"""Write each workflow as a Send to Amazon "File upload" sheet.

Upload only into a FRESH workflow: switching an in-progress workflow to file upload
clears everything already staged.
"""
import os
import re

from inbound import config, xlsx


def sheet_rows(workflow):
    rows = [list(pair) for pair in config.STA_DEFAULTS]
    rows.append([])
    rows.append(list(config.STA_HEADER))
    for r in workflow["skus"]:
        rows.append([r["sku"], r["qty"], config.PREP_OWNER, config.LABELING_OWNER])
    return rows


def filename(workflow):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", workflow["name"]).strip("_") + ".xlsx"


def write_all(stage, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for wf in stage["workflows"]:
        path = os.path.join(out_dir, filename(wf))
        xlsx.write(path, config.STA_SHEET_NAME, sheet_rows(wf))
        paths.append(path)
    return paths
