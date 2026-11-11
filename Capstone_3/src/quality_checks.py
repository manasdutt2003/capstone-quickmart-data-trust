"""Enterprise data-quality rule framework (Sprint 1).

Every rule is named, counted and given a treatment. Rules operate on
raw-text DataFrames and return boolean fail masks.
"""


from .normalise import (
    parse_date,
    parse_discount_frac,
    parse_float,
    parse_int,
    valid_email,
)

PLACEHOLDERS = {"NA", "N/A", "na", "n/a", "-", "--", "unknown", "UNKNOWN",
                "Unknown", "null", "NULL", "None", "none", "?", "MISSING",
                "missing"}


def is_missing_or_placeholder(series):
    s = series.astype(str)
    return s.str.strip().eq("") | s.str.strip().isin(PLACEHOLDERS)


def fail_empty_or_placeholder(series):
    return is_missing_or_placeholder(series)


def check_customers(df):
    """Run all customer quality checks."""
    checks = {}
    checks["QC_CUST_ID_DUP"] = df["customer_id"].astype(str).duplicated(
        keep=False)
    checks["QC_CUST_NAME_MISSING"] = is_missing_or_placeholder(
        df["customer_name"])
    checks["QC_CUST_EMAIL_INVALID"] = ~df["email"].astype(str).apply(
        lambda v: valid_email(v, PLACEHOLDERS))
    checks["QC_CUST_CITY_MISSING"] = is_missing_or_placeholder(df["city"])
    checks["QC_CUST_PHONE_INVALID"] = ~df["phone"].astype(str).apply(
        lambda x: len("".join(filter(str.isdigit, x))) >= 10
        if x.strip() and x.strip() not in PLACEHOLDERS else True)
    checks["QC_CUST_SIGNUP_UNPARSEABLE"] = df["signup_date"].astype(str).apply(
        lambda x: parse_date(x) is None
        if x.strip() and x.strip() not in PLACEHOLDERS else True)
    return checks


def check_products(df):
    """Run all product quality checks."""
    checks = {}
    checks["QC_PROD_ID_DUP"] = df["product_id"].astype(str).duplicated(
        keep=False)
    checks["QC_PROD_NAME_MISSING"] = is_missing_or_placeholder(
        df["product_name"])
    checks["QC_PROD_CAT_MISSING"] = is_missing_or_placeholder(df["category"])
    checks["QC_PROD_PRICE_INVALID"] = df["unit_price"].astype(str).apply(
        lambda x: parse_float(x) is None or parse_float(x) <= 0)
    checks["QC_PROD_STOCK_INVALID"] = df["stock_qty"].astype(str).apply(
        lambda x: parse_int(x) is None
        or (parse_int(x) is not None and parse_int(x) < 0))
    return checks


def check_orders(df, customers, products, today="2026-10-11"):
    """Run all order quality checks with referential integrity."""
    checks = {}
    cust_ids = set(customers["customer_id"].astype(str).str.strip())
    prod_ids = set(products["product_id"].astype(str).str.strip())

    checks["QC_ORD_ID_DUP"] = df["order_id"].astype(str).duplicated(keep=False)
    checks["QC_ORD_CUST_FK_BROKEN"] = ~df["customer_id"].astype(str).str.strip(
        ).isin(cust_ids)
    checks["QC_ORD_PROD_FK_BROKEN"] = ~df["product_id"].astype(str).str.strip(
        ).isin(prod_ids)
    checks["QC_ORD_DATE_INVALID"] = df["order_date"].astype(str).apply(
        lambda x: parse_date(x) is None)
    checks["QC_ORD_DATE_FUTURE"] = df["order_date"].astype(str).apply(
        lambda x: parse_date(x) is not None
        and parse_date(x).isoformat() > today)
    checks["QC_ORD_QTY_INVALID"] = df["quantity"].astype(str).apply(
        lambda x: parse_int(x) is None or parse_int(x) <= 0)
    checks["QC_ORD_PRICE_INVALID"] = df["unit_price_paid"].astype(str).apply(
        lambda x: parse_float(x) is None or parse_float(x) < 0)
    checks["QC_ORD_DISC_INVALID"] = df["discount"].astype(str).apply(
        lambda x: parse_discount_frac(x) is None
        if x.strip() and x.strip() not in PLACEHOLDERS else False)
    checks["QC_ORD_STATUS_MISSING"] = is_missing_or_placeholder(
        df["order_status"])
    checks["QC_ORD_PAYMENT_MISSING"] = is_missing_or_placeholder(
        df["payment_mode"])
    checks["QC_ORD_DELIVERY_INVALID"] = df["delivery_days"].astype(str).apply(
        lambda x: parse_int(x) is None
        or (parse_int(x) is not None
            and (parse_int(x) < 0 or parse_int(x) > 30)))
    # Backwards-compatible aliases for the cleaned-pipeline rule names.
    checks["QC_ORD_STATUS_BLANK"] = checks["QC_ORD_STATUS_MISSING"]
    checks["QC_ORD_PAYMENT_BLANK"] = checks["QC_ORD_PAYMENT_MISSING"]
    return checks


def quality_fail_masks(customers, products, orders, today="2026-10-11"):
    """Return {rule_name: boolean Series} (alias for run_all_checks)."""
    return run_all_checks(customers, products, orders, today)


def run_all_checks(customers, products, orders, today="2026-10-11"):
    """Run all quality checks and return combined dict."""
    all_checks = {}
    all_checks.update(check_customers(customers))
    all_checks.update(check_products(products))
    all_checks.update(check_orders(orders, customers, products, today))
    return all_checks


class Rule:
    def __init__(self, name, predicate, treatment):
        self.name = name
        self.predicate = predicate
        self.treatment = treatment


RULE_CATALOG = [
    {"rule_id": "QC_CUST_ID_DUP", "table": "customers",
     "column": "customer_id",
     "predicate": "customer_id appears more than once",
     "treatment": "QUARANTINE", "name": "QC_CUST_ID_DUP"},
    {"rule_id": "QC_CUST_NAME_MISSING", "table": "customers",
     "column": "customer_name",
     "predicate": "customer_name is missing or placeholder",
     "treatment": "QUARANTINE", "name": "QC_CUST_NAME_MISSING"},
    {"rule_id": "QC_CUST_EMAIL_INVALID", "table": "customers",
     "column": "email", "predicate": "email format invalid or placeholder",
     "treatment": "QUARANTINE", "name": "QC_CUST_EMAIL_INVALID"},
    {"rule_id": "QC_CUST_CITY_MISSING", "table": "customers",
     "column": "city", "predicate": "city is missing or placeholder",
     "treatment": "NORMALISE", "name": "QC_CUST_CITY_MISSING"},
    {"rule_id": "QC_CUST_PHONE_INVALID", "table": "customers",
     "column": "phone", "predicate": "phone has <10 digits",
     "treatment": "COUNT", "name": "QC_CUST_PHONE_INVALID"},
    {"rule_id": "QC_CUST_SIGNUP_UNPARSEABLE", "table": "customers",
     "column": "signup_date",
     "predicate": "signup_date unparseable or placeholder",
     "treatment": "QUARANTINE", "name": "QC_CUST_SIGNUP_UNPARSEABLE"},
    {"rule_id": "QC_PROD_ID_DUP", "table": "products",
     "column": "product_id",
     "predicate": "product_id appears more than once",
     "treatment": "QUARANTINE", "name": "QC_PROD_ID_DUP"},
    {"rule_id": "QC_PROD_NAME_MISSING", "table": "products",
     "column": "product_name", "predicate": "product_name missing",
     "treatment": "QUARANTINE", "name": "QC_PROD_NAME_MISSING"},
    {"rule_id": "QC_PROD_CAT_MISSING", "table": "products",
     "column": "category", "predicate": "category missing",
     "treatment": "NORMALISE", "name": "QC_PROD_CAT_MISSING"},
    {"rule_id": "QC_PROD_PRICE_INVALID", "table": "products",
     "column": "unit_price", "predicate": "unit_price missing, text, or <=0",
     "treatment": "QUARANTINE", "name": "QC_PROD_PRICE_INVALID"},
    {"rule_id": "QC_PROD_STOCK_INVALID", "table": "products",
     "column": "stock_qty", "predicate": "stock_qty negative or non-integer",
     "treatment": "COUNT", "name": "QC_PROD_STOCK_INVALID"},
    {"rule_id": "QC_ORD_ID_DUP", "table": "orders", "column": "order_id",
     "predicate": "order_id appears more than once",
     "treatment": "QUARANTINE", "name": "QC_ORD_ID_DUP"},
    {"rule_id": "QC_ORD_CUST_FK_BROKEN", "table": "orders",
     "column": "customer_id", "predicate": "customer_id not in customers",
     "treatment": "QUARANTINE", "name": "QC_ORD_CUST_FK_BROKEN"},
    {"rule_id": "QC_ORD_PROD_FK_BROKEN", "table": "orders",
     "column": "product_id", "predicate": "product_id not in products",
     "treatment": "QUARANTINE", "name": "QC_ORD_PROD_FK_BROKEN"},
    {"rule_id": "QC_ORD_DATE_INVALID", "table": "orders",
     "column": "order_date", "predicate": "order_date unparseable",
     "treatment": "QUARANTINE", "name": "QC_ORD_DATE_INVALID"},
    {"rule_id": "QC_ORD_DATE_FUTURE", "table": "orders",
     "column": "order_date", "predicate": "order_date > 2026-10-11",
     "treatment": "QUARANTINE", "name": "QC_ORD_DATE_FUTURE"},
    {"rule_id": "QC_ORD_QTY_INVALID", "table": "orders",
     "column": "quantity", "predicate": "quantity not positive integer",
     "treatment": "QUARANTINE", "name": "QC_ORD_QTY_INVALID"},
    {"rule_id": "QC_ORD_PRICE_INVALID", "table": "orders",
     "column": "unit_price_paid",
     "predicate": "unit_price_paid missing or negative",
     "treatment": "QUARANTINE", "name": "QC_ORD_PRICE_INVALID"},
    {"rule_id": "QC_ORD_DISC_INVALID", "table": "orders",
     "column": "discount", "predicate": "discount unparseable",
     "treatment": "COUNT", "name": "QC_ORD_DISC_INVALID"},
    {"rule_id": "QC_ORD_STATUS_MISSING", "table": "orders",
     "column": "order_status", "predicate": "order_status missing",
     "treatment": "NORMALISE", "name": "QC_ORD_STATUS_MISSING"},
    {"rule_id": "QC_ORD_PAYMENT_MISSING", "table": "orders",
     "column": "payment_mode", "predicate": "payment_mode missing",
     "treatment": "NORMALISE", "name": "QC_ORD_PAYMENT_MISSING"},
    {"rule_id": "QC_ORD_DELIVERY_INVALID", "table": "orders",
     "column": "delivery_days",
     "predicate": "delivery_days negative or >30",
     "treatment": "QUARANTINE", "name": "QC_ORD_DELIVERY_INVALID"},
]
