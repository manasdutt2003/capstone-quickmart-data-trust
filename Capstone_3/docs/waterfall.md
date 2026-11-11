# Waterfall: raw rows to trusted orders

| stage | rows_in | rows_removed | rows_out | independent_removed |
|---|---|---|---|---|
| raw | 6103 | 0 | 6103 |  |
| loaded | 6103 | 0 | 6103 |  |
| deduped | 6103 | 103 | 6000 |  |
| R01 | 6000 | 198 | 5802 | 198 |
| R02 | 5802 | 153 | 5649 | 159 |
| R03 | 5649 | 1807 | 3842 | 1851 |
| R04 | 3842 | 407 | 3435 | 833 |
| R05 | 3435 | 427 | 3008 | 718 |
| R06 | 3008 | 2371 | 637 | 4636 |
| R07 | 637 | 55 | 582 | 561 |
| R08 | 582 | 53 | 529 | 623 |
| R09 | 529 | 0 | 529 | 0 |
| R10 | 529 | 7 | 522 | 75 |
| R11 | 522 | 0 | 522 | 0 |
| R12 | 522 | 0 | 522 | 175 |
| trusted_lenient | 522 | 0 | 522 |  |
| strict | 522 | 407 | 115 |  |

Sequential attribution runs R01 first ... R12 last; each rule removes FAIL rows still remaining. Independent counts run each rule on the full input; the gap is rows failing multiple rules, attributed to the first catcher. WARNING never removes.

# Join row-count log

| join | left_rows | right_rows | out_rows | dropped |
|---|---|---|---|---|
| orders-customers-city | 6000 | 499 | 6000 | 0 |
| orders-products-category | 6000 | 30 | 6000 | 0 |
| orders-customers-city | 522 | 499 | 522 | 0 |
| orders-products-category | 522 | 30 | 522 | 0 |
| orders-customers-city | 5478 | 499 | 5478 | 0 |
| orders-products-category | 5478 | 30 | 5478 | 0 |
