from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id


def test_collection_constants_match_schema_ssot() -> None:
    assert c.PRODUCTS == "products"
    assert c.LISTINGS == "listings"
    assert c.PRICE_HISTORY == "price_history"


def test_listing_document_id_rule() -> None:
    assert build_listing_document_id("SSG", "1000832367906") == "SSG_1000832367906"
