---
name: "mfn-label-run"
description: "Process Instrumentpro's Amazon seller-fulfilled (MFN) orders: cross-check Amazon (DataDoe), Listing Mirror and Veeqo, drop MCF orders, bulk-buy labels, print labels AND packing slips, and generate the USPS scan form. Decisions are made by the bundled mfn code; Claude gathers data, runs it, and gets Michael's go."
---

# MFN label run (Amazon seller-fulfilled orders)

**The `mfn` code in this skill makes every decision.** Claude's job is to fetch data
from the connectors into files, run the commands, show Michael the result, and do
the browser/printer steps the code cannot do yet. Never decide by hand what the
code decides: which orders to buy, which rate, OnTrac switches, whether printing
is complete. If a command refuses, report the refusal — do not work around it.

Run commands from this skill's folder: `python3 -m mfn <step> ...`. Keep all files
for a run in one working folder (`run/` below). The ledger lives at
`state/ledger.jsonl` and must persist between runs — it is what stops a label
being bought twice.

## Ground rules
- Michael reviews; Claude executes. Every buy needs his fresh yes **with the approval code**.
- No computer use (screen takeover) — it blanks all his monitors.
- Runs are manual; Chrome and DirectPrint must be open on the office PC.
- Buying prints nothing. The run is not done until `print-check` passes.

## 0. Pre-flight (stop at the first failure, buy nothing)
1. Office Chrome: deviceId 4a9d76f6-8f01-444e-b8e5-f4ca6bdc1a56 ("Mike San Leandro Work Office"). `switch_browser` once if missing, then `select_browser` and `tabs_context_mcp` with createIfEmpty (opens a NEW WINDOW).
2. DirectPrint: app.veeqo.com/settings/devices/documents shows "Connected" with 4X6 Zebra and Canon Printer after ~15 s. If not, Michael reopens DirectPrint (or ends "OpenJDK Platform binary").
3. Veeqo login: a bounce to /signin needs Michael to click Login with Amazon > Allow himself.
4. `lm_list_integrations` returns store 9554. If not, stop (no scraping fallback).
5. `veeqo_get_account_capabilities`: `features.plan.printing.direct_print` and `permissions.manage_shipping`. Always pass ids explicitly.
6. DataDoe: `sellers_and_vendors_list` returns "Instrumentpro US" (id eddaeeb5-59bb-490b-b76c-82c56d65804f).

## 1. Gather data, then reconcile
Save each raw response verbatim as JSON:
- `run/veeqo.json` ← `veeqo_list_orders(channel_ids=159514, status="awaiting_fulfillment", page_size=100, field_groups="fulfilmentState")` (all pages merged into one `results` list)
- `run/lm.json` ← `lm_get_order_fulfillment_channels(orderIds=<order numbers>, integrationConfigId=9554, startDate=<14 days before oldest>, endDate=<today>)` (max 50 ids per call; merge `results`)
- `run/amazon.json` ← DataDoe export of source `89b27535d2` (Order Line Items), last 14 days, filters `fulfillment_channel = Merchant` AND `amazon_order_status beginsWith Unshipped`, columns at least `amazon_order_id, sku, amazon_order_status`; save the rows array. If DataDoe is down, use `--no-amazon` and tell Michael the Amazon check was skipped.

```
python3 -m mfn reconcile --veeqo run/veeqo.json --lm run/lm.json --amazon run/amazon.json --out run/recon.json
```
It prints the allocation ids to quote. Held orders (MCF, Listing Mirror unknown,
international, not on Amazon's list, already labelled) are never quoted. If Michael
explicitly releases an order held for review, re-run with `--include <order number>`
(MCF, international and already-labelled orders cannot be released).

## 2. Customs gate (international orders only)
`reconcile` holds every international order (Puerto Rico counts). The API quotes
these even when the UI blocks them on customs, so the UI decides: open the order
row in Veeqo; "Fix errors to continue shipping" / greyed Buy label means customs is
incomplete — usually the HS code. Do not invent an HS code (automated HS coding is
coming in a later version of this code). Once fixed and the row shows a real rate,
Michael can have it included in a follow-up run.

## 3. Quote, plan, approve
For each allocation id: `veeqo_get_allocation_rates(allocation_id=..., max_results=3)`.
Save them as `run/quotes.json` = `{"<allocation_id>": <full response>, ...}`.
```
python3 -m mfn plan --recon run/recon.json --quotes run/quotes.json --out run/plan.json
```
Send Michael the printed message exactly. It ends with **"Approve with code XXXXXXXX"**.
Optionally run `veeqo_buy_shipping_labels_bulk(..., dry_run=True)` with the payload
from step 4 first. **Stop until Michael replies with the code.**

## 4. Buy
```
python3 -m mfn check-buy --plan run/plan.json --code <code from Michael> --ledger state/ledger.jsonl --out run/payload.json
```
Only if it exits 0: call `veeqo_buy_shipping_labels_bulk` with `carrier` and `items`
copied **verbatim** from `run/payload.json`. If it refuses (expired quotes, code
mismatch, already bought), report it; for expired quotes re-quote, re-plan and get a
new code. Poll `veeqo_get_bulk_shipment_result` until `settled` (not `complete`),
save it to `run/result.json`, then **always**:
```
python3 -m mfn record-buy --plan run/plan.json --result run/result.json --ledger state/ledger.jsonl
```
Never re-submit a batch. Failed items may still be charged; they stay blocked in the
ledger until Michael decides.

## 5. Print — labels AND packing slips
```
python3 -m mfn print-plan --plan run/plan.json --ledger state/ledger.jsonl --prefs run/prefs.json
```
(`run/prefs.json` ← `veeqo_get_printing_preferences`). Make each listed
`veeqo_generate_order_document` call exactly as given (one template per call).
Poll `veeqo_list_print_jobs` until ready, save it to `run/jobs.json`, push each PDF to
the printer named in the plan with QZ (notes below), then:
```
python3 -m mfn print-check --plan run/plan.json --ledger state/ledger.jsonl --prefs run/prefs.json --jobs run/jobs.json --printed <job ids sent> --out run/print_check.json
```
Exit 1 means something is not printed — it lists what. Keep going until it passes.

## 6. USPS scan form (Canon)
1. app.veeqo.com/shipping/manifests?carrier=amazon_shipping_v2 → Carrier USPS, ship-from 94578, 14417 E 14th St. → Generate form. Close the blob tab it opens; wait ~8 s and reload.
2. Patch `URL.createObjectURL` to keep the blob and `window.open` to no-op, `.click()` today's row's Download (date and time run together, e.g. "Oct 066:33 PM" — match loosely), base64 the blob and `qz.print(qz.configs.create('Canon Printer'), [{type:'pixel', format:'pdf', flavor:'base64', data:<b64>}])`. Restore `window.open`.
3. Confirm with Michael it came out.

## 7. Report
```
python3 -m mfn report --plan run/plan.json --ledger state/ledger.jsonl --print-check run/print_check.json --scan-form yes
```
Send it, then check `veeqo_list_orders(channel_ids=159514, status="awaiting_fulfillment", count_only=True)` shows only held orders. Close tabs opened for the run.

## QZ / DirectPrint notes
- `const qz = window.qz || window.qzUtil.qz` (`window.qz` on settings/devices/documents; `window.qzUtil` there and on shipping/manifests).
- On the manifests page call `await window.qzUtil.connectQzTray()` if `qz.websocket.isActive()` is false.
- Base64 PDFs in `0x8000` chunks. Send PDFs only — HTML crashes DirectPrint.
- Printers: Canon Printer, 4X6 Zebra, 3X1 Zebra, Microsoft Print to PDF, OneNote.
- Fallback: hand Michael the `documentUrls` to Ctrl+P to "4X6 Zebra".

## Also watch — stuck MCF orders
`lm_list_mcf_orders(fulfillmentChannel="MCF", startDate=<14 days ago>, endDate=<today>)`: rows not Complete/Cancelled, over a day old, with null `fulfillment_time`. Mention; don't act.
