from src import normalise as N


def test_norm_id():
    assert N.norm_id(" p-10 ") == "P10"


def test_email_invalid():
    assert not N.valid_email("NA", {"NA"})
    assert not N.valid_email("no-at-sign", set())
    assert N.valid_email("a@b.com", set())


def test_discount_forms():
    assert N.parse_discount_frac("10%") == 0.10
    assert N.parse_discount_frac("0.1") == 0.10
    assert N.parse_discount_frac("15") == 0.15
    assert N.parse_discount_frac("20 percent") == 0.20
    assert N.parse_discount_frac("") is None


def test_date_formats():
    assert str(N.parse_date("2024-01-25")) == "2024-01-25"
    assert N.parse_date("unknown") is None
    assert N.parse_date("") is None