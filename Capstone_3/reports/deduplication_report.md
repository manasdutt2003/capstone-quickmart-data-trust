# Deduplication report

Rules D01-D06 applied (D06 flags for review only, never removes).

rule_id
D01    103
D03     21

Commission:  commission_before  commission_after  commission_leakage  orders_before  orders_after  rows_removed
         1266157.9        1258401.62             7756.28           6103          6000           103

Reconciliation: raw_orders=6103 clean_orders=6000 removed=103 (rows in = rows out + rows set aside).

Leakage concentration: see commission_compare_city.csv (by city), commission_compare_month.csv (by month), commission_compare_payment.csv and commission_compare_status.csv.
