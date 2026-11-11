import pandas as pd

from src.cleaning import clean_all


def _raw():
    c = pd.DataFrame([{
        "customer_id": " C1 ", "customer_name": " A ", "email": "A@B.COM ",
        "city": "bengaluru ", "phone": " 999 ", "signup_date": "06/26/2025"}])
    p = pd.DataFrame([{
        "product_id": " P-10 ", "product_name": " X ", "category": "GROCERY ",
        "unit_price": "?60", "stock_qty": "NA"}])
    o = pd.DataFrame([{
        "order_id": " O1 ", "customer_id": "C1", "product_id": "P-10",
        "order_date": "2024-02-01", "quantity": "2", "unit_price_paid": "1,200",
        "discount": "10%", "payment_mode": "cod ", "order_status": "delivered",
        "delivery_days": "3", "notes": " ok "}])
    city = {"bengaluru": "Bengaluru", "": "MISSING"}
    cat = {"GROCERY": "Grocery", "": "MISSING"}
    status = {"delivered": "Delivered", "": "MISSING"}
    pay = {"cod": "COD", "": "MISSING"}
    return c, p, o, city, cat, status, pay


def test_cleaning_standardises_and_preserves_raw():
    c, p, o, city, cat, status, pay = _raw()
    cc, pc, oc = clean_all(c, p, o, city, cat, status, pay)
    assert cc.loc[0, "city"] == "Bengaluru"
    assert cc.loc[0, "email"] == "a@b.com"
    assert cc.loc[0, "signup_date"] == "2025-06-26"
    assert pc.loc[0, "unit_price"] == "60"
    assert pc.loc[0, "stock_qty"] == ""
    assert oc.loc[0, "unit_price_paid"] == "1200"
    assert oc.loc[0, "discount"] == "0.1"
    assert oc.loc[0, "payment_mode"] == "COD"
    assert oc.loc[0, "order_status"] == "Delivered"
    # lineage preserved
    assert cc.loc[0, "raw_city"] == "bengaluru "
    assert oc.loc[0, "_source_row"] == 1


def test_cleaning_never_drops_rows():
    c, p, o, city, cat, status, pay = _raw()
    cc, pc, oc = clean_all(c, p, o, city, cat, status, pay)
    assert len(cc) == len(c) and len(pc) == len(p) and len(oc) == len(o)


def test_placeholders_become_empty():
    c, p, o, city, cat, status, pay = _raw()
    o.loc[0, "discount"] = "NA"
    o.loc[0, "order_date"] = "unknown"
    _, _, oc = clean_all(c, p, o, city, cat, status, pay)
    assert oc.loc[0, "discount"] == ""
    assert oc.loc[0, "order_date"] == ""
    assert oc.loc[0, "raw_discount"] == "NA"


def test_invalid_and_edge_case_cleaning():
    """Explicitly test that incorrect formats are cleaned to empty strings 
    and complex valid formats parse correctly.
    """
    c, p, o, city, cat, status, pay = _raw()
    
    # 1. Test invalid / unparseable dates return ""
    o.loc[0, "order_date"] = "sdvgs"
    _, _, oc = clean_all(c, p, o, city, cat, status, pay)
    assert oc.loc[0, "order_date"] == "", "Invalid date should be cleaned to empty string"

    # 2. Test valid alternative date formats parse correctly to ISO (YYYY-MM-DD)
    o.loc[0, "order_date"] = "24 November 2026"
    _, _, oc = clean_all(c, p, o, city, cat, status, pay)
    assert oc.loc[0, "order_date"] == "2026-11-24", "Verbose date formats should parse to ISO YYYY-MM-DD"

    # 3. Test invalid currency / numeric formats return ""
    p.loc[0, "unit_price"] = "invalid_price"
    _, pc, _ = clean_all(c, p, o, city, cat, status, pay)
    assert pc.loc[0, "unit_price"] == "", "Invalid currency format should be cleaned to empty string"

    # 4. Test accounting format currency: (1500) => -1500
    p.loc[0, "unit_price"] = "(1500)"
    _, pc, _ = clean_all(c, p, o, city, cat, status, pay)
    assert pc.loc[0, "unit_price"] == "-1500", "Accounting format parentheses should convert to negative numbers"

    # 5. Test currency with symbols, commas, and decimals
    p.loc[0, "unit_price"] = "$1,250.50"
    _, pc, _ = clean_all(c, p, o, city, cat, status, pay)
    assert pc.loc[0, "unit_price"] == "1250.5", "Currency with symbols and commas should canonicalise properly"
