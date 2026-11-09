# Dataset source and transformations

## Source and license

- Requested source repository: [ratharin1223-lab/UCI-online-Retail-Dataset](https://github.com/ratharin1223-lab/UCI-online-Retail-Dataset), pinned commit `08cab3abecf21bcb00c4698de10324dfe50ec9c8`.
- Downloaded file: `Online Retail.xlsx` (sheet `Online Retail`), 23,715,344 bytes; downloaded 2026-11-04 to `data/online_retail.xlsx`.
- The linked repository provides an MIT `LICENSE`; the underlying UCI dataset is attributed to Daqing Chen and distributed under **CC BY 4.0** by the UCI Machine Learning Repository. Citation: Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. Retain this attribution and license when redistributing the data.
- Official UCI description: UK-based non-store online retailer transactions from 2010-12-01 through 2011-12-09; 541,909 rows and eight source columns.
- In the retrieved workbook there are 1,454 missing descriptions, 135,080 missing CustomerIDs, 9,288 C-prefixed cancellation lines, and 10,624 lines with negative quantity. These rows/values are retained.

## SQLite preparation and canonical view

`scripts/prepare_dataset.py` imports the original workbook to `data/online_retail.sqlite`, table `retail_transactions`, and creates `sales_facts`. All 541,909 input rows are retained; missing customer IDs and descriptions are not dropped. Customer IDs are represented as text, and dates are stored in ISO format.

The canonical view provides:

- `order_date`, `year`, `quarter`, `month`: from `InvoiceDate` using calendar periods.
- `product_name`: `Description`; missing descriptions display as `StockCode: <code>` in the view. The original description remains null in the source table.
- `product_id`: `StockCode`.
- `category_name`: `NULL`; no category is present in this dataset.
- `region`: `Country`; no sub-country region is present.
- `quantity`: original `Quantity`.
- `revenue`: `Quantity * UnitPrice`, in GBP. Negative quantities and cancellation invoices are retained, yielding negative net adjustments. The view also exposes invoice number, stock code, customer ID, unit price, and `is_cancellation`.

No product costs exist, so profit/margin are unavailable. This preparation does not apply the linked repository README's described cleaning/filtering: the actual pinned repository contains the original workbook and no tracked `data/online_retail_clean.csv`.
