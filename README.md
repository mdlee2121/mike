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

### Roadmap

1. **Core logic** (this): works with today's Cowork connectors.
2. **HS codes**: code book per SKU, validated against the official US tariff schedule.
3. **Direct API clients**: Veeqo, DataDoe, Listing Mirror, PrintNode, so no browser is needed.
4. **Cloud schedule**: runs on a timer, sends Michael the plan, buys on approval; later, auto-approves runs that meet his rules.
