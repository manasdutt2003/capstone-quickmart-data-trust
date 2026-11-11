# Quality summary

                   rule_id   extract     table          column                       rule                               predicate  fail_count  count  treatment                                                                      reason  pass_count
            QC_CUST_ID_DUP customers customers     customer_id             QC_CUST_ID_DUP      customer_id appears more than once          40     40 QUARANTINE             Sprint-1 quality gate; see quality_summary.md (QC_CUST_ID_DUP).         480
      QC_CUST_NAME_MISSING customers customers   customer_name       QC_CUST_NAME_MISSING customer_name is missing or placeholder          20     20 QUARANTINE       Sprint-1 quality gate; see quality_summary.md (QC_CUST_NAME_MISSING).         500
     QC_CUST_EMAIL_INVALID customers customers           email      QC_CUST_EMAIL_INVALID     email format invalid or placeholder          57     57 QUARANTINE      Sprint-1 quality gate; see quality_summary.md (QC_CUST_EMAIL_INVALID).         463
      QC_CUST_CITY_MISSING customers customers            city       QC_CUST_CITY_MISSING          city is missing or placeholder          39     39  NORMALISE       Sprint-1 quality gate; see quality_summary.md (QC_CUST_CITY_MISSING).         481
     QC_CUST_PHONE_INVALID customers customers           phone      QC_CUST_PHONE_INVALID                    phone has <10 digits           0      0      COUNT      Sprint-1 quality gate; see quality_summary.md (QC_CUST_PHONE_INVALID).         520
QC_CUST_SIGNUP_UNPARSEABLE customers customers     signup_date QC_CUST_SIGNUP_UNPARSEABLE  signup_date unparseable or placeholder          25     25 QUARANTINE Sprint-1 quality gate; see quality_summary.md (QC_CUST_SIGNUP_UNPARSEABLE).         495
            QC_PROD_ID_DUP  products  products      product_id             QC_PROD_ID_DUP       product_id appears more than once           0      0 QUARANTINE             Sprint-1 quality gate; see quality_summary.md (QC_PROD_ID_DUP).          30
      QC_PROD_NAME_MISSING  products  products    product_name       QC_PROD_NAME_MISSING                    product_name missing           0      0 QUARANTINE       Sprint-1 quality gate; see quality_summary.md (QC_PROD_NAME_MISSING).          30
       QC_PROD_CAT_MISSING  products  products        category        QC_PROD_CAT_MISSING                        category missing           1      1  NORMALISE        Sprint-1 quality gate; see quality_summary.md (QC_PROD_CAT_MISSING).          29
     QC_PROD_PRICE_INVALID  products  products      unit_price      QC_PROD_PRICE_INVALID        unit_price missing, text, or <=0           2      2 QUARANTINE      Sprint-1 quality gate; see quality_summary.md (QC_PROD_PRICE_INVALID).          28
     QC_PROD_STOCK_INVALID  products  products       stock_qty      QC_PROD_STOCK_INVALID       stock_qty negative or non-integer          14     14      COUNT      Sprint-1 quality gate; see quality_summary.md (QC_PROD_STOCK_INVALID).          16
             QC_ORD_ID_DUP    orders    orders        order_id              QC_ORD_ID_DUP         order_id appears more than once         206    206 QUARANTINE              Sprint-1 quality gate; see quality_summary.md (QC_ORD_ID_DUP).        5897
     QC_ORD_CUST_FK_BROKEN    orders    orders     customer_id      QC_ORD_CUST_FK_BROKEN            customer_id not in customers         483    483 QUARANTINE      Sprint-1 quality gate; see quality_summary.md (QC_ORD_CUST_FK_BROKEN).        5620
     QC_ORD_PROD_FK_BROKEN    orders    orders      product_id      QC_ORD_PROD_FK_BROKEN              product_id not in products         456    456 QUARANTINE      Sprint-1 quality gate; see quality_summary.md (QC_ORD_PROD_FK_BROKEN).        5647
       QC_ORD_DATE_INVALID    orders    orders      order_date        QC_ORD_DATE_INVALID                  order_date unparseable         290    290 QUARANTINE        Sprint-1 quality gate; see quality_summary.md (QC_ORD_DATE_INVALID).        5813
        QC_ORD_DATE_FUTURE    orders    orders      order_date         QC_ORD_DATE_FUTURE                 order_date > 2026-10-11         467    467 QUARANTINE         Sprint-1 quality gate; see quality_summary.md (QC_ORD_DATE_FUTURE).        5636
        QC_ORD_QTY_INVALID    orders    orders        quantity         QC_ORD_QTY_INVALID           quantity not positive integer         651    651 QUARANTINE         Sprint-1 quality gate; see quality_summary.md (QC_ORD_QTY_INVALID).        5452
      QC_ORD_PRICE_INVALID    orders    orders unit_price_paid       QC_ORD_PRICE_INVALID     unit_price_paid missing or negative         267    267 QUARANTINE       Sprint-1 quality gate; see quality_summary.md (QC_ORD_PRICE_INVALID).        5836
       QC_ORD_DISC_INVALID    orders    orders        discount        QC_ORD_DISC_INVALID                    discount unparseable           0      0      COUNT        Sprint-1 quality gate; see quality_summary.md (QC_ORD_DISC_INVALID).        6103
     QC_ORD_STATUS_MISSING    orders    orders    order_status      QC_ORD_STATUS_MISSING                    order_status missing         629    629  NORMALISE      Sprint-1 quality gate; see quality_summary.md (QC_ORD_STATUS_MISSING).        5474
    QC_ORD_PAYMENT_MISSING    orders    orders    payment_mode     QC_ORD_PAYMENT_MISSING                    payment_mode missing         564    564  NORMALISE     Sprint-1 quality gate; see quality_summary.md (QC_ORD_PAYMENT_MISSING).        5539
   QC_ORD_DELIVERY_INVALID    orders    orders   delivery_days    QC_ORD_DELIVERY_INVALID           delivery_days negative or >30         266    266 QUARANTINE    Sprint-1 quality gate; see quality_summary.md (QC_ORD_DELIVERY_INVALID).        5837

Scorecard:
    table  rows  columns  total_cells  checks_run  failed_cells  quality_score_pct
customers   520       18         9360           6           181              98.07
 products    30       16          480           5            17              96.46
   orders  6103       28       170884          13          5472              96.80
