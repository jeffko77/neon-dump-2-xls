# Invoice PDF Format Specification

Shareable reference for reproducing the **Girls Lacrosse / Field Hockey Scheduler** invoice PDF layout. This document describes the visual structure, typography, data fields, and business rules used by the invoice app in this repo.

**Reference sample:** `Invoice  - Wentzville Lacrosse Club.pdf` (project root)  
**Reference implementation:** `app/invoice/invoice_pdf.py`  
**Logo asset:** `static/invoice-logo.png` (722×512 px PNG; includes Gateway Arch graphic + caption text)

---

## Page setup

| Property | Value |
|---|---|
| Page size | US Letter (8.5″ × 11″) |
| Margins | 0.55″ on all sides |
| Content width | 7.4″ (letter width minus margins) |
| Background | White |
| Color | Black text and rules only |

---

## Document structure (top to bottom)

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER (3 columns, vertically middle-aligned)              │
│  [Payee block]     [Logo centered]     [Contact block]      │
├─────────────────────────────────────────────────────────────┤
│  (0.2″ vertical gap)                                        │
├─────────────────────────────────────────────────────────────┤
│  BILL TO (2 columns)                                        │
│  TO: School name …… Invoice Number ……                      │
│  Street address …… Invoice Date ……                         │
│  City, ST ZIP                                               │
├─────────────────────────────────────────────────────────────┤
│  (0.15″ vertical gap)                                      │
├─────────────────────────────────────────────────────────────┤
│  SPORT INVOICE TITLE (centered, bold)                       │
├─────────────────────────────────────────────────────────────┤
│  LINE ITEMS TABLE                                           │
├─────────────────────────────────────────────────────────────┤
│  NOTE: … (optional, bold)                                   │
├─────────────────────────────────────────────────────────────┤
│  Payment instructions + payee address                         │
│  THANK YOU FOR YOUR BUSINESS (centered, bold)               │
└─────────────────────────────────────────────────────────────┘
```

---

## Section 1 — Header (3-column row)

Single table row with three cells. All cells are **vertically middle-aligned**.

### Column widths

| Column | Width | Alignment |
|---|---|---|
| Payee (left) | 2.35″ | Left |
| Logo (center) | 2.7″ (remaining space) | Center |
| Contact (right) | 2.35″ | Right |

### Left column — Payee / remittance address

```
EMILY LOVERCHECK          ← bold
444 Royal Village
Manchester, MO 63011
```

| Field | Value |
|---|---|
| Name | `EMILY LOVERCHECK` |
| Address line 1 | `444 Royal Village` |
| City/state/ZIP | `Manchester, MO 63011` |

### Center column — Logo

| Property | Value |
|---|---|
| File | `static/invoice-logo.png` |
| Native size | 722 × 512 px |
| Display width | **2.5″** (50% of original 5″ design width) |
| Display height | 2.5″ × (512 ÷ 722) ≈ **1.77″** |
| Alignment | Horizontally and vertically centered in the middle column |
| Fallback | If no logo file, render centered text: `Girls Lacrosse / Field Hockey Scheduler` |

The logo image already contains the caption **“Girls Lacrosse / Field Hockey Scheduler”** — do not duplicate that text when the logo is present.

### Right column — Contact

```
                    Contact:
   elovercheck@parkwayschools.net
```

Right-aligned within the column.

---

## Section 2 — Bill to

Two-column table below the header (after **0.2″** gap).

| Column | Width | Alignment |
|---|---|---|
| School address | 4.0″ | Left |
| Invoice metadata | 3.5″ | Right |

### Row 1

| Left | Right |
|---|---|
| **TO:** {SchoolName} | Invoice Number {invoiceNumber} |

### Row 2

| Left | Right |
|---|---|
| {Street address} | Invoice Date: {invoiceDate} |

### Row 3

| Left | Right |
|---|---|
| {City}, {State} {ZIP} | *(empty)* |

**City line format:** `{city}, {state} {zip}` — omit missing parts gracefully.

---

## Section 3 — Invoice title

Centered, bold, 12 pt. Text depends on sport:

| Sport | Title |
|---|---|
| Lacrosse | `LACROSSE SCHEDULING INVOICE` |
| Field Hockey | `FIELD HOCKEY SCHEDULING INVOICE` |

Spacing: 12 pt before, 8 pt after.

---

## Section 4 — Line items table

Two columns:

| Column | Width | Alignment |
|---|---|---|
| ITEM (description) | 4.7″ | Left |
| DESCRIPTION (amount) | 1.8″ | Right |

### Header row

| ITEM | DESCRIPTION |
|---|---|
| **ITEM** (bold) | **DESCRIPTION** (bold) |

Bold rule (1 pt black) under header row.

### Line item rules

Amounts formatted as `$1,234.56` (USD, 2 decimal places, thousands separator).

#### Lacrosse invoices — always show these three lines

| Line label | Amount field |
|---|---|
| `Schedule Preparation for Lacrosse - Spring {seasonYear}` | `base_amount` |
| `C Team Scheduling` | `c_team_scheduling` |
| `Ranking Services` | `ranking_services` |

Show **$0.00** lines even when zero (matches original Access/PDF behavior).

#### Field Hockey invoices — always show these two lines

| Line label | Amount field |
|---|---|
| `Schedule Preparation for Field Hockey - Fall {seasonYear}` | `base_amount` |
| `FH Ranking Services` | `fh_ranking_services` |

#### Additional lines (either sport) — only when amount > 0

| Line label | Amount field |
|---|---|
| `Revision` | `revision_amount` |
| `Dual-Sport Fee` | `dual_sport_fee` |
| `Ranking Services` | `ranking_services` *(Field Hockey only, if > 0)* |
| `C Team Scheduling` | `c_team_scheduling` *(Field Hockey only, if > 0)* |

### Total row

| Left cell | Right cell |
|---|---|
| *(empty)* | **{total}** (bold) |

Rules under the last item row (0.5 pt) and under the total row (1 pt).

**Total calculation:**

```
total = base_amount
      + revision_amount
      + dual_sport_fee
      + ranking_services
      + c_team_scheduling
      + fh_ranking_services
```

---

## Section 5 — Notes (optional)

If present, render one bold line:

```
NOTE: {collection_status}
```

If `collection_status` is empty, fall back to `address_note` with the same `NOTE:` prefix.

Common values from legacy data:

- `SECOND REQUEST: Please Pay Promptly`
- `PLEASE NOTE THE CHANGE TO PAYABLE ADDRESS`

---

## Section 6 — Payment footer

After **0.2″** gap:

```
Please make check payable to:
EMILY LOVERCHECK
444 Royal Village
Manchester, MO 63011
```

After **0.15″** gap, centered bold closing line:

```
THANK YOU FOR YOUR BUSINESS
```

---

## Typography

| Style | Font | Size | Weight | Notes |
|---|---|---|---|---|
| Body | Helvetica | 11 pt | Normal | Leading 13 pt |
| Bold body | Helvetica-Bold | 11 pt | Bold | Payee name, table headers, total |
| Section title | Helvetica-Bold | 12 pt | Bold | Invoice title, thank-you line |
| Right-aligned body | Helvetica | 11 pt | Normal | Invoice number/date columns |

No colors other than black. No italics.

---

## Standard fee amounts

These are the canonical fee options (from the legacy Access database):

| Fee | Standard values |
|---|---|
| Base schedule preparation | $110.00 |
| Revision | $0 or $50 |
| Dual-sport (Lacrosse + Field Hockey) | $0 or $100 |
| Ranking services (Lacrosse) | $0 or $12 |
| C-team scheduling (Lacrosse) | $0 or $20 |
| FH ranking services | $0 or $15 |

---

## Invoice number and date

### Invoice number

1. If invoice notes contain `Invoice Number {value}`, use that value verbatim.  
   Example: `202637LX`
2. Otherwise generate: `{seasonYear}{invoiceId:03d}{sportCode}`  
   - Lacrosse → `LX`  
   - Field Hockey → `FH`  
   - Example: `2026288LX`

Display label: `Invoice Number {number}` (no colon).

### Invoice date

1. If invoice notes contain `Invoice Date {value}`, use that value verbatim.  
   Example: `6/15/2026`
2. Otherwise use the invoice `created_at` timestamp formatted as `M/D/YYYY` (US style, no leading zeros required).

Display label: `Invoice Date: {date}` (with colon).

Notes field format when both are stored:

```
Invoice Number 202637LX | Invoice Date 6/15/2026
```

---

## Output filename

```
Invoice - {SchoolName}.pdf
```

Sanitize the school name: remove non-alphanumeric characters (except spaces/hyphens), replace spaces with underscores.

Example: `Invoice - Wentzville_Lacrosse_Club.pdf`

---

## Data model (minimum fields needed)

### School (bill-to)

| Field | Example |
|---|---|
| `school_name` | Wentzville Lacrosse Club |
| `address` | 18 Normandy Drive |
| `city` | Lake St. Louis |
| `state` | MO |
| `zip` | 63367 |

### Invoice

| Field | Type | Example |
|---|---|---|
| `sport` | string | Lacrosse |
| `season_year` | int | 2026 |
| `base_amount` | decimal | 110.00 |
| `revision_amount` | decimal | 0.00 |
| `dual_sport_fee` | decimal | 0.00 |
| `ranking_services` | decimal | 0.00 |
| `c_team_scheduling` | decimal | 0.00 |
| `fh_ranking_services` | decimal | 0.00 |
| `collection_status` | string | SECOND REQUEST: Please Pay Promptly |
| `address_note` | string | *(optional alternate note)* |
| `notes` | string | Invoice Number … \| Invoice Date … |
| `created_at` | ISO datetime | fallback for date |

---

## API endpoint (this app)

```
GET /api/invoices/{invoice_id}/pdf
```

Returns `application/pdf` with `Content-Disposition: attachment`.

---

## Checklist for matching the reference PDF

- [ ] US Letter, 0.55″ margins
- [ ] Three-column header: payee | logo | contact
- [ ] Logo 2.5″ wide, vertically centered between text blocks
- [ ] Bill-to block with TO/address left, invoice #/date right
- [ ] Sport-specific centered title in ALL CAPS
- [ ] Lacrosse shows base + C-team + ranking lines (including $0.00)
- [ ] Field Hockey shows base + FH ranking lines
- [ ] Total right-aligned under DESCRIPTION column
- [ ] NOTE line when collection status is set
- [ ] Payable-to footer + thank-you line
- [ ] Helvetica 11 pt body, 12 pt titles

---

## Files to copy into another project

| File | Purpose |
|---|---|
| `static/invoice-logo.png` | Header logo (required for matching layout) |
| `Invoice  - Wentzville Lacrosse Club.pdf` | Visual reference / acceptance test |
| `app/invoice/invoice_pdf.py` | Working ReportLab implementation |
| `app/invoice/invoice_settings.py` | Payee/contact constants |
