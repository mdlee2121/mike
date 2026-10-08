"""Standing settings for staging an invoice into Send to Amazon.

Every rule Michael has set lives here, so a change is one edit with a test,
not a sentence buried in a skill file.
"""

# One SKU under this many units disqualifies the whole shipment from Amazon-optimized
# placement, so those SKUs go in their own "Part 2" workflow (Michael, Sep 2026).
MIN_UNITS_OPTIMIZED = 5

# Workflow names: "<Vendor> <Invoice#>" and "<Vendor> <Invoice#> Part 2".
PART2_SUFFIX = " Part 2"

# "Who preps / who labels" on every row. Units are labelled by us.
PREP_OWNER = "Seller"
LABELING_OWNER = "Seller"

# Send to Amazon "File upload" template layout. Amazon owns this format: if an upload
# is rejected, compare against a freshly downloaded template and fix it here.
STA_SHEET_NAME = "Create workflow – template"
STA_DEFAULTS = (
    ("Default prep owner", PREP_OWNER),
    ("Default labeling owner", LABELING_OWNER),
)
STA_HEADER = (
    "Merchant SKU", "Quantity", "Prep owner", "Labeling owner",
    "Units per box", "Number of boxes",
    "Box length (in)", "Box width (in)", "Box height (in)", "Box weight (lb)",
    "Expiration date (MM/DD/YYYY)",
)
