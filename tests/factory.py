"""Builders for source responses, shaped exactly like the live Veeqo, Listing Mirror and
DataDoe responses captured on Oct 7 2026. Customer details are made up."""
import itertools

_ids = itertools.count(1000)


def veeqo_order(number, sku="DADEXL125MU", international=False, weight=16, alloc_id=None,
                shipment_id=None, can_ship=True, channel_id=159514, allocations=None):
    oid = next(_ids)
    if allocations is None:
        allocations = [{
            "id": alloc_id or next(_ids), "warehouseId": 87917, "shipmentId": shipment_id,
            "hasDimensions": True,
            "package": {"weight": weight, "weightUnit": "oz", "width": 4.33, "height": 1,
                        "depth": 4.41, "dimensionsUnit": "inches"},
        }]
    return {
        "id": oid, "orderNumber": number, "status": "awaiting_fulfillment",
        "channelId": channel_id, "channelName": "Amazon Channel",
        "shippingAddress": {"firstName": "Test", "lastName": "Buyer", "city": "OAKLAND",
                            "state": "CA", "postcode": "94601", "country": "US"},
        "deliveryMethod": {"id": 514518, "name": "Standard"},
        "lineItems": [{"id": next(_ids), "quantity": 1, "sku": sku, "productName": sku}],
        "allocations": allocations,
        "allocatedCompletely": True, "canBeShipped": can_ship,
        "international": international, "fulfilledByAmazon": False,
    }


def veeqo_list(*orders):
    return {"results": list(orders), "summary": {"totalCount": len(orders)}}


def lm_response(**verdicts):
    """lm_response(**{"113-...": "MFN"}) -> lm_get_order_fulfillment_channels response."""
    rows = []
    for order_id, verdict in verdicts.items():
        row = {"orderId": order_id, "verdict": verdict, "isMcf": verdict == "MCF"}
        if verdict != "unknown":
            row.update(lmStatus="Accepted", lmOrderId=next(_ids))
        rows.append(row)
    return {"window": {"integrationConfigId": 9554}, "results": rows}


def datadoe_rows(*order_ids):
    return [{"amazon_order_id": o, "sku": "X", "quantity": 1, "amazon_order_status": "Unshipped"}
            for o in order_ids]


def rate(title="USPS Ground Advantage (less than 1lb)", charge="6.07", carrier="usps",
         sub="USPS", promise=True, service_type=None, vas=False):
    return {
        "carrier": "amazon_shipping_v2",
        "serviceType": service_type or f"amazon_shipping_v2-{title[:8]}",
        "serviceTitle": title, "remoteShipmentId": "prb2a30ae83",
        "serviceCarrier": carrier, "subCarrierId": sub, "totalNetCharge": charge,
        "currency": "USD", "meetsDeliveryPromise": promise,
        "requiresValueAddedServiceChoice": vas,
    }


def quote(*rates, expires="2026-10-07T06:59:59.976Z"):
    return {"available": list(rates), "unavailable": [], "quotesExpireAt": expires}


PREFS = {
    "preferenceId": "packingSlip", "title": "Shipping Label and Packing Slip",
    "documentSize": "4x6", "orientation": "portrait", "integrated": False,
    "templates": [{"format": "shipping_labels", "name": "shipping_labels"},
                  {"format": "packing_slip", "name": "[Veeqo]packing_slip"}],
}


def print_job(job_id, orders, fmt, name=None, status="document_ready"):
    return {"jobId": str(job_id), "status": status, "identifier": ", ".join(orders),
            "templates": [{"name": name or fmt, "format": fmt}],
            "documentUrls": [f"https://example.invalid/{job_id}.pdf"] if status == "document_ready" else [],
            "failures": None}
