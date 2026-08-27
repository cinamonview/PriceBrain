def test_repository_modules_import() -> None:
    import pricebrain_app.repository as repository
    from pricebrain_app.repository import (  # noqa: F401
        ListingRepository,
        PriceHistoryRepository,
        ProductRepository,
    )
    from pricebrain_app.repository.crawl_repository import CrawlRepository
    from pricebrain_app.repository.gpu_repository import GpuRepository
    from pricebrain_app.repository.mall_repository import MallRepository
    from pricebrain_app.repository.seller_repository import SellerRepository
    from pricebrain_app.repository.validation_repository import ValidationRepository

    assert CrawlRepository.__name__ == "CrawlRepository"
    assert GpuRepository.__name__ == "GpuRepository"
    assert MallRepository.__name__ == "MallRepository"
    assert SellerRepository.__name__ == "SellerRepository"
    assert ValidationRepository.__name__ == "ValidationRepository"
    assert "save_validated_product" not in repository.__all__
