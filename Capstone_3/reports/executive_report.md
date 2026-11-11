# Executive report (trusted delivered orders only)

Grand delivered value Rs 2,309,394.00 across 799 orders.

## Top 5 customers
customer_id  city_std  orders    value first_order last_order
      C0438    Mysuru       4 244965.0  2024-12-19 2026-07-04
      C0359    Mysuru       6 242836.0  2024-04-09 2026-07-23
      C0477 Bengaluru       2 241050.0  2025-10-05 2026-01-06
      C0416      Pune       2 193280.0  2026-02-09 2026-03-17
      C0402   Chennai       2 160096.0  2025-07-07 2026-08-21

## Sales mart head
order_month  city_std category_std  orders  units  value
    2022-06 Hyderabad      Grocery       1      5  750.0
    2022-09      Pune      MISSING       1      5 5400.0
    2024-01 Bengaluru Dairy & Eggs       2      3  609.0
    2024-01 Bengaluru      Grocery       5     13 1683.0
    2024-01 Bengaluru       Snacks       1      3  450.0

City/category/month totals reconcile to the grand total (see reconciliation_report.md).

## Limits
1. Stock report unreliable (many blank/negative stock_qty).
2. Delivery estimates unreliable for non-Delivered rows (empty/invalid days).
3. Customer-city answers exclude FK-broken orders (city unknown).
