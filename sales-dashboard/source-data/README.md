# Source data — column contract

Drop CSVs here (or anywhere — the dashboard uses a file picker, not a fetch). The dashboard classifies files by filename:

- Filename contains `header` → loaded as table `invoice_header`
- Filename contains `detail` → loaded as table `invoice_detail`
- Filename contains `account`, `customer`, `client`, or `party` → loaded as table `accounts`

## invoice_header.csv

| Column | Type | Required | Notes |
|---|---|---|---|
| `invoice_id` | string/int | yes | Unique per invoice |
| `account_id` | string/int | yes | FK to `accounts.account_id` |
| `invoice_date` | date (YYYY-MM-DD) | yes | Used for monthly/annual aggregations |
| `subtotal` | numeric | yes | Sum of line items, pre-tax and pre-discount |
| `discount_amount` | numeric | yes | Discount applied to the invoice (0 if none) |
| `tax_amount` | numeric | yes | Sales tax |
| `total_amount` | numeric | yes | Final billed amount: `subtotal − discount_amount + tax_amount` |

**Revenue convention:** the dashboard's pre-baked queries currently treat `total_amount` as "revenue." If net-of-tax reporting is required, swap to `SUM(subtotal - discount_amount)` in the SQL templates.

## invoice_detail.csv

| Column | Type | Required | Notes |
|---|---|---|---|
| `invoice_id` | string/int | yes | FK to `invoice_header.invoice_id` |
| `line_id` | string/int | no | Unique within invoice |
| `description` | text | recommended | Used for service classification if `category` absent |
| `category` | text | recommended | If present, used directly for Q5 service segmentation |
| `quantity` | numeric | no | |
| `unit_price` | numeric | no | |
| `line_amount` | numeric | yes | Line extended total |

## accounts.csv

Optional but unlocks Q1 (parent-org rollup), Q4, Q9, Q10, Q11. Without it the dashboard falls back to raw account ids.

| Column | Type | Required | Notes |
|---|---|---|---|
| `account_id` | string/int | yes | |
| `account_name` | text | yes | Display name |
| `parent_account_name` | text | if hierarchy exists | NULL for top-level accounts; set to the parent's name for child accounts. Drives Q1 (Chicago Co-op parent rollup) and Q4 (count of fleets under a parent). |
| `segment` | text | no | e.g. `'Fleet'` — populate if not all revenue is Fleet revenue (Q2). |
| `status` | text | no | e.g. `Active` / `Cancelled` |
| `signup_date` | date | no | |
| `cancelled_date` | date | if any cancellations | NULL for active accounts. Required for Q9, Q10. |
| `cancellation_reason` | text | if any cancellations | Free-text or enum. Required for Q11. |

## Notes for the analyst producing the extract

- UTF-8, comma-delimited, double-quoted text, header row on line 1. DuckDB's `read_csv_auto` handles the usual variations but unusual date formats may need `DATE_FORMAT` hints.
- Dates as `YYYY-MM-DD` is safest. US `MM/DD/YYYY` also parses but check a few rows after load.
- Money columns: no currency symbols, no thousands separators — just numbers. Commas in amount fields break CSVs.
- For the hierarchy: if a customer like "Chicago Co-op Fleet Services" has many sub-fleet accounts, every sub-fleet row should have `parent_account_name = 'Chicago Co-op Fleet Services'` and the sub-fleet's own name in `account_name`. The parent itself either appears as its own row with `parent_account_name = NULL`, or doesn't appear at all — either works.
