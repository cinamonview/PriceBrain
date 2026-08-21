# GPU Catalog

PriceBrain GPU Catalog defines operator-managed GPU products that are seeded into the `crawler_targets` collection. Catalog seeding does not crawl SSG or write to `products`, `listings`, or `price_history`.

## Purpose

```text
GPU Catalog
     ↓
Target Management (seed / bulk enable-disable)
     ↓
crawler_targets
     ↓
Scheduler → Worker → SSGCrawler → IngestClient → FastAPI → Pipeline → Firestore
```

Catalog JSON is the operator-facing source of truth for **configuration fields** only. Operational crawl state remains owned by the Worker lifecycle.

## JSON schema

Each catalog file is a JSON array of objects:

| Field | Required | Description |
| --- | --- | --- |
| `mall_id` | yes | Supported mall (`ssg`) |
| `product_url` | yes | Product detail URL (use validated SSG URL in operational files) |
| `external_product_id` | no | Operator-defined external ID (alphanumeric, `.`, `_`, `-`) |
| `product_name` | no | Display name |
| `brand` | no | Vendor/brand label (also stored as a tag when absent) |
| `category` | no | Catalog category (`gpu` recommended) |
| `tags` | no | String array for filtering (`rtx5080`, `nvidia`, etc.) |
| `priority` | no | Integer 1–1000 (default 50) |
| `enabled` | no | Boolean (default `true`) |
| `crawl_interval_seconds` | no | Crawl interval (default 3600) |

Example (`docs/examples/gpu_targets.example.json`):

```json
[
  {
    "mall_id": "ssg",
    "external_product_id": "example-rtx5080-001",
    "product_name": "Example RTX 5080",
    "category": "gpu",
    "tags": ["rtx5080", "nvidia", "16gb"],
    "priority": 100,
    "enabled": true,
    "product_url": "https://example.com/products/example-rtx5080-001"
  }
]
```

Example files use `https://example.com/...` placeholders only. Replace URLs with validated SSG product URLs before operational seeding.

## Validation

Each entry is validated independently:

- `mall_id` required and must be supported
- `product_url` required with valid `http`/`https` format
- mall-specific URL validation (`ssg.com` product URL for `mall_id=ssg`)
- `priority` must be integer 1–1000
- `tags` must be a string array
- `enabled` must be boolean
- `external_product_id` must match `[A-Za-z0-9._-]{1,128}` when present

Invalid entries increment `invalid` and are reported without aborting the entire file.

## Seed

```bash
python -m pricebrain_app.scripts.seed_gpu_targets \
  --file docs/examples/gpu_targets.example.json
```

Summary output:

```text
Seed Summary
total: 10
created: 7
updated: 3
skipped: 0
invalid: 0
```

JSON output:

```bash
python -m pricebrain_app.scripts.seed_gpu_targets --file my_gpu_catalog.json --json
```

Seed is idempotent:

- no duplicate documents
- `target_id` unchanged (`ssg_{itemId}` for SSG)
- operational fields preserved on merge

### Operational field preservation

Seed merge updates catalog configuration only:

- `product_url`, `mall_id`, `enabled`, `crawl_interval_seconds`
- `product_name`, `external_product_id`, `category`, `tags`, `priority`

Seed does **not** overwrite:

- `last_crawled_at`, `next_crawl_at`
- `last_status`, `last_error_code`, `last_error_message`, `last_crawled_price`
- `crawl_status`, `lease_owner`, `lease_until`

Unchanged entries are counted as `skipped`.

## Dry-run

Preview validation and planned changes without Firestore writes:

```bash
python -m pricebrain_app.scripts.seed_gpu_targets \
  --file my_gpu_catalog.json \
  --dry-run
```

Dry-run performs Firestore reads for duplicate detection but does not call write APIs.

## Enable / disable

Bulk configuration changes:

```bash
python -m pricebrain_app.scripts.set_crawl_targets \
  --mall ssg \
  --tag rtx5080 \
  --enabled false
```

This changes `enabled` only. It does not modify crawl history or lease state.

## Filter and inspect

```bash
python -m pricebrain_app.scripts.list_crawl_targets \
  --category gpu \
  --tag rtx5080 \
  --mall ssg \
  --enabled \
  --priority-min 80 \
  --json
```

GPU catalog statistics:

```bash
python -m pricebrain_app.scripts.list_crawl_targets --catalog-stats
python -m pricebrain_app.scripts.crawler_status
```

Example stats:

```text
GPU Catalog
--------------------
total: 20
enabled: 17
disabled: 3

RTX 5080: 8
RTX 5070: 6
Other: 6
```

## Priority

Due targets are ordered by:

```text
priority DESC
target_id ASC
```

Worker `max_targets_per_cycle` uses this order via `CrawlTargetRepository.list_due()` without modifying Worker logic.

## Using real product URLs

1. Copy `docs/examples/gpu_targets.example.json` to an operator-local file (do not commit).
2. Replace `https://example.com/...` with validated SSG product URLs.
3. Run `--dry-run` first.
4. Run seed against Firestore.

Never commit real URLs, API keys, or Firebase credentials.

## Security

- Do not commit `.env`, `secrets/`, or service account JSON
- Do not hardcode `PRICEBRAIN_INGEST_API_KEY` or Bearer tokens
- Example JSON and docs use placeholder URLs only
- CLI output redacts configured secrets via existing ops redaction helpers

## Related docs

- `docs/CRAWL_TARGET_MANAGEMENT.md`
- `docs/CRAWLER_OPERATIONS.md`
