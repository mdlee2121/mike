"""Standing settings for staging an invoice into Send to Amazon.

Every rule Michael has set lives here, so a change is one edit with a test,
not a sentence buried in a skill file.
"""

# One SKU under this many units disqualifies the whole shipment from Amazon-optimized
# placement, so those SKUs go in their own "Part 2" workflow (Michael, Sep 2026).
MIN_UNITS_OPTIMIZED = 5

# Workflow names: "<Vendor> <Invoice#>" and "<Vendor> <Invoice#> Part 2".
PART2_SUFFIX = " Part 2"

# Send to Amazon "File upload" template, copied cell for cell from Amazon's
# ManifestFileUpload_Template_IncludeCasePack_IncludeExpirationDate_IncludeMLC_MPL.xlsx
# (downloaded Oct 2026). Header texts keep Amazon's trailing spaces. If an upload is
# rejected, download a fresh template and compare it with this.
STA_SHEET_NAME = "Create workflow – template"
STA_NOTE = "Please review the Example tab before you complete this sheet"   # row 1

# Rows 3-4. "Seller" is the only value Amazon accepts: it offers no prep or labelling.
PREP_OWNER = "Seller"
LABELING_OWNER = "Seller"
STA_DEFAULTS = (
    ("Default prep owner", PREP_OWNER),
    ("Default labeling owner", LABELING_OWNER),
)

STA_GROUP_ROW = (None, None, "Optional", None, "Optional: Use only for case-packed SKUs")  # row 7
STA_HEADER = (                                                                             # row 8
    "Merchant SKU", "Quantity", "Expiration date (MM/DD/YYYY)", "Manufacturing lot code ",
    "Units per box ", "Number of boxes",
    "Box length (in)", "Box width (in)", "Box height (in)", "Box weight (lb)",
)
STA_FIRST_DATA_ROW = 9
