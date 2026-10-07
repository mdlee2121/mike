"""Standing settings for the MFN label run.

Every rule Michael has set lives here, so a change is one edit with a test,
not a sentence buried in a skill file.
"""

# Veeqo
AMAZON_CHANNEL_ID = 159514        # "Amazon Channel" — seller-fulfilled orders
AMAZON_FBA_CHANNEL_ID = 185260    # never used by this run
CARRIER = "amazon_shipping_v2"    # every label is bought through Amazon Buy Shipping

# Listing Mirror
LM_AMAZON_STORE_ID = 9554

# Carriers we never buy (Michael, Sep 28 2026, until he says otherwise).
# Matched case-insensitively against serviceCarrier, subCarrierId and serviceTitle.
BANNED_CARRIERS = ("ontrac",)

# A carrier switch is called out when the replacement costs this much more.
SWITCH_ALERT_DOLLARS = 2.00
SWITCH_ALERT_PERCENT = 0.20

# "Expedited service on a light package" flag (e.g. FedEx 2Day on a 1 lb order).
LIGHT_PACKAGE_OZ = 16.0
EXPEDITED_WORDS = ("2day", "2nd day", "next day", "overnight", "express")

# Printers (names as PrintNode / DirectPrint list them)
LABEL_PRINTER = "4X6 Zebra"
LETTER_PRINTER = "Canon Printer"

# Templates that carry a shipping label. Veeqo fails the whole print batch if a
# label template and a non-label template are requested in the same call.
LABEL_TEMPLATE_FORMATS = ("shipping_labels",)
