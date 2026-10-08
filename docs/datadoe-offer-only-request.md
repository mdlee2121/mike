# Request to DataDoe: offer-only listing creation

**To:** DataDoe support
**Subject:** Feature request: offer-only option (LISTING_OFFER_ONLY) for AMAZON_LISTINGS_CREATE

Hi DataDoe team,

We use the `AMAZON_LISTINGS_CREATE` Action to list products on our Amazon seller
account (Instrumentpro US). It works well for brand-new products. In September it
created two Takamine guitars cleanly.

Most of our new listings, though, are for ASINs that already exist in Amazon's
catalog. We only need to add our own offer: SKU, condition, price and FBA
fulfillment channel. Amazon's Listings Items API supports this with
`requirements=LISTING_OFFER_ONLY` on `putListingsItem`, and the JSON listings feed
supports the same `requirements` value per message.

Today `AMAZON_LISTINGS_CREATE` has no `requirements` field and validates every
change against the full product-type schema. An offer-only payload for an existing
guitar ASIN (B00009J580) is rejected in dry run with about 30 missing product
attributes (back, top, neck, fretboard, bullet_point, item_package_dimensions and
so on). None of these are needed to add an offer.

Could you add an optional `requirements` field (`LISTING`, `LISTING_OFFER_ONLY`,
`LISTING_PRODUCT_ONLY`) to `AMAZON_LISTINGS_CREATE`, pass it through to Amazon, and
validate against the matching requirement set? With `LISTING_OFFER_ONLY`, the
payload would be roughly:

```json
{"sku": "YAMJR1", "productType": "GUITARS",
 "requirements": "LISTING_OFFER_ONLY",
 "attributes": {
   "merchant_suggested_asin": [{"value": "B00009J580", "marketplace_id": "ATVPDKIKX0DER"}],
   "condition_type": [{"value": "new_new", "marketplace_id": "ATVPDKIKX0DER"}],
   "fulfillment_availability": [{"fulfillment_channel_code": "AMAZON_NA"}],
   "purchasable_offer": [{"currency": "USD", "audience": "ALL",
     "our_price": [{"schedule": [{"value_with_tax": 199.99}]}],
     "marketplace_id": "ATVPDKIKX0DER"}]}}
```

This would let us take listing creation out of the browser completely.

Thanks,

Michael Lee
President
Instrumentpro.Com Inc.
www.instrumentpro.com
(925)683-6135
