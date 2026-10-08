# Instrumentpro automation

Code that makes Instrumentpro's Claude skills reliable: the code makes the
decisions, and Claude gathers data, handles judgment calls and gets approval.

## `mfn` — Amazon seller-fulfilled label run

Replaces the hand-run decision steps of the `mfn-label-run` skill.

```
reconcile  -> plan -> [Michael approves code] -> check-buy -> (buy) -> record-buy
           -> print-plan -> (print) -> print-check -> report
```

| Step | Guarantees |
|---|---|
| `reconcile` | MCF, Listing Mirror "unknown", international, already-labelled and not-on-Amazon orders are never quoted. Orders on Amazon but missing from Veeqo are flagged. |
| `plan` | First rate wins; OnTrac is swapped for the next rate and reported. Charges are numbers. Produces an approval code fingerprinting exactly what will be bought. |
| `check-buy` | The only source of a buy payload. Refuses a wrong code, a plan edited after approval, expired quotes, or any allocation already in the ledger. |
| `record-buy` | Writes every attempted allocation to `state/ledger.jsonl`, failures included, so nothing is ever bought twice. |
| `print-plan` / `print-check` | One document call per template; the run isn't done until every order has its label **and** packing slip printed. |
| `report` | The same summary every run. |

Rules Michael has set (channel ids, banned carriers, printers) are in `mfn/config.py`.

### Run the tests

```
python3 -m unittest discover -s tests -t .
```

No third-party packages are needed (Python 3.10+).

### Package the skill for Cowork

```
scripts/package_skill.sh
```
Builds `dist/mfn-label-run.zip` with `SKILL.md` and the `mfn` code, ready to upload.

## `inbound` — Send to Amazon upload files

Replaces step 8 of the `invoice-to-inbound` skill (searching and adding SKUs one by
one) with one file upload per workflow. It stops at "Choose inventory to send",
the same place the skill does; no shipment is built through the API.

```
python3 -m inbound sta-file --input lines.json --out-dir run/<vendor>-<invoice>
```

`lines.json` is the units in hand, with each SKU's FNSKU from DataDoe:

```json
{"vendor": "Radial", "invoice": "INV38499",
 "lines": [{"sku": "RADR8001100A", "asin": "B0...", "fnsku": "X00...", "qty": 40}]}
```

| Guarantee | |
|---|---|
| Under-5 split | SKUs under 5 units go in `<Vendor> <Invoice#> Part 2`; the rest in `<Vendor> <Invoice#>`. |
| Barcode check | A SKU whose FNSKU is blank or equals the ASIN is held back with the reason, never put in a file. |
| Counter check | Prints the exact "SKUs ready to send: N (M units)" the page should show after upload. |

Upload each file into a **fresh** workflow only: switching a workflow that already
has SKUs to file upload clears it. The layout in `inbound/config.py` is copied cell
for cell from Amazon's template (Oct 2026). Units go in as individual units; the
case-pack, expiration and lot columns are left blank. The template has no prep
category, so a new SKU's "Prep and labeling details needed" flag still has to be
cleared on the page.

### Roadmap

1. **Core logic** (this): works with today's Cowork connectors.
2. **HS codes**: code book per SKU, validated against the official US tariff schedule.
3. **Direct API clients**: Veeqo, DataDoe, Listing Mirror, PrintNode, so no browser is needed.
4. **Cloud schedule**: runs on a timer, sends Michael the plan, buys on approval; later, auto-approves runs that meet his rules.
