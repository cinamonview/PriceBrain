# Crawl Target Management

PriceBrain crawl targets live in the Firestore `crawler_targets` collection. This document describes how to register GPU (and other) products as crawl targets, manage them in bulk, and how target management relates to the Scheduler and Worker.

## Collection: `crawler_targets`

Each document ID equals `target_id` (stable, derived from mall + product URL).

| Field | Description |
| --- | --- |
| `target_id` | Stable ID (SSG: `ssg_{itemId}`) |
| `mall_id` | Mall identifier (e.g. `ssg`) |
| `product_url` | Canonical product detail URL |
| `external_product_id` | Mall-specific product ID (SSG: `itemId`) |
| `product_name` | Human-readable catalog name (optional) |
| `enabled` | Whether scheduler/worker may crawl this target |
| `crawl_interval_seconds` | Minimum interval between crawls (default: 3600) |
| `priority` | Scheduler ordering hint when worker limits batch size (default: 50) |
| `category` | Catalog category (e.g. `gpu`) |
| `tags` | String tags for filtering (e.g. `rtx5080`, `nvidia`) |
| `created_at` / `updated_at` | Audit timestamps |
| `last_crawled_at` / `next_crawl_at` | Operational crawl schedule |
| `last_status` / `last_error_code` / `last_error_message` | Last crawl outcome |
| `last_crawled_price` | Last observed price |
| `crawl_status` / `lease_until` / `lease_owner` | Worker lease state |

Operational fields are updated only by the Worker/Scheduler crawl lifecycle. Seed and bulk enable/disable commands touch configuration fields only.

## Target ID rule (do not change)

SSG targets use:

```text
ssg_{itemId}
```

Example URL `https://example.com/products/gpu-placeholder-1` with a valid SSG product URL at seed time → `ssg_{itemId}`.

## Register a single target

```bash
python -m pricebrain_app.scripts.register_crawl_target \
  --mall ssg \
  --url "https://example.com/products/gpu-placeholder-1" \
  --interval 3600
```

Replace the placeholder URL with a validated SSG product URL before running against Firestore.

Use `--disabled` to register without immediate scheduling pressure.

## Bulk seed GPU targets

Prepare a JSON array (see `docs/examples/gpu_targets.example.json`):

```json
[
  {
    "mall_id": "ssg",
    "product_url": "https://example.com/products/gpu-placeholder-1",
    "product_name": "Example GPU Placeholder 1",
    "category": "gpu",
    "tags": ["nvidia", "rtx5080", "example-vendor"],
    "crawl_interval_seconds": 3600,
    "enabled": true,
    "priority": 100
  }
]
```

Replace placeholder URLs with validated SSG product URLs in operational seed files.

Run seed (register/merge only — **no HTTP crawl**):

```bash
python -m pricebrain_app.scripts.seed_gpu_targets \
  --file docs/examples/gpu_targets.example.json
```

Output:

```json
{
  "created": 1,
  "updated": 0,
  "errors": []
}
```

Re-running the same file is idempotent:

```json
{
  "created": 0,
  "updated": 1,
  "errors": []
}
```

### What seed updates vs preserves

**Updated on merge:** `product_url`, `mall_id`, `enabled`, `crawl_interval_seconds`, `product_name`, `external_product_id`, `category`, `tags`, `priority`, `updated_at`.

**Preserved on merge:** `last_crawled_at`, `next_crawl_at`, `last_status`, `last_error_code`, `last_error_message`, `last_crawled_price`, lease fields, `created_at`.

## List and inspect targets

```bash
python -m pricebrain_app.scripts.list_crawl_targets --mall ssg --category gpu --enabled
python -m pricebrain_app.scripts.list_crawl_targets --tag rtx5080 --json
python -m pricebrain_app.scripts.show_crawl_target --target-id ssg_EXAMPLE_ITEM_ID --json
```

Filters:

- `--mall` — mall_id
- `--category` — exact category match
- `--tag` — tag membership (case-insensitive)
- `--enabled` / `--disabled`
- `--due` / `--failed` — operational state
- `--json` — machine-readable output

## Bulk enable / disable

Change configuration only; does not delete `products`, `listings`, or `price_history`.

```bash
python -m pricebrain_app.scripts.set_crawl_targets \
  --mall ssg \
  --tag rtx5080 \
  --enabled false
```

At least one filter (`--mall`, `--category`, or `--tag`) is required.

## Category and tags

- `category` is stored lowercase (e.g. `gpu`).
- `tags` is a string array; use consistent tags for bulk operations (`rtx5080`, `nvidia`, vendor names).
- Filtering is case-insensitive for tags.

## Relationship to Scheduler

The Scheduler selects **due** enabled targets via `CrawlTargetRepository.list_due()`. When the Worker applies `max_targets_per_cycle`, due targets are ordered by **descending `priority`**, then `target_id`.

Seed/bulk commands do not run crawls or alter due-time logic beyond setting `enabled` and `crawl_interval_seconds`.

## Relationship to Worker

The Worker claims due targets with a short lease, runs the mall adapter (SSG), updates operational fields via `update_after_crawl`, and optionally ingests successful payloads.

Target management does not invoke the Worker or SSG HTTP client.

## Operational notes

1. **SSG HTTP 403** — Real SSG access may return HTTP 403. The crawler maps this to `SSG_ACCESS_DENIED`, updates the target operational fields, releases the lease, and exits cleanly. Do not bypass or mask 403 in target management.
2. **Disabled targets** — Remain in Firestore; scheduler/worker skip them.
3. **Re-seeding** — Safe for catalog metadata; does not reset crawl history.
4. **Secrets** — Never commit `.env`, Firebase credentials, or API keys. Example JSON uses placeholder URLs only (`https://example.com/...`).

## Related docs

- `docs/CRAWLER_OPERATIONS.md` — status, failures, schedule views
- `docs/CRAWLER_OPERATIONAL_GATE.md` — operational gate tests
