from pathlib import Path

import pandas as pd

from app.pipeline import cleaning

FIXTURE = Path(__file__).parent / "fixtures" / "transactions_sample.csv"


def test_normalize_date_both_formats():
    assert cleaning.normalize_date("04-09-2024") == "2024-09-04"
    assert cleaning.normalize_date("2024/02/05") == "2024-02-05"


def test_normalize_date_unparseable_returns_none():
    assert cleaning.normalize_date("not a date") is None
    assert cleaning.normalize_date("") is None
    assert cleaning.normalize_date(None) is None


def test_strip_amount_removes_dollar_sign():
    assert cleaning.strip_amount("$11325.79") == 11325.79
    assert cleaning.strip_amount("6874.1") == 6874.1
    assert cleaning.strip_amount("1,234.5") == 1234.5


def test_strip_amount_non_numeric_returns_none():
    assert cleaning.strip_amount("") is None
    assert cleaning.strip_amount("abc") is None


def test_normalize_uppercases_status_and_currency():
    df = pd.DataFrame(
        {
            "txn_id": ["T1"],
            "date": ["04-09-2024"],
            "merchant": ["Swiggy"],
            "amount": ["100"],
            "currency": ["inr"],
            "status": ["success"],
            "category": ["Food"],
            "account_id": ["ACC001"],
            "notes": [""],
        }
    )
    clean, _ = cleaning.normalize(df)
    assert clean.loc[0, "currency"] == "INR"
    assert clean.loc[0, "status"] == "SUCCESS"


def test_normalize_fills_missing_category():
    df = pd.DataFrame(
        {
            "txn_id": ["T1"],
            "date": ["04-09-2024"],
            "merchant": ["Amazon"],
            "amount": ["100"],
            "currency": ["INR"],
            "status": ["SUCCESS"],
            "category": [""],
            "account_id": ["ACC001"],
            "notes": [""],
        }
    )
    clean, _ = cleaning.normalize(df)
    assert clean.loc[0, "category"] == cleaning.UNCATEGORISED


def test_dedupe_removes_exact_duplicates_only():
    df = pd.DataFrame(
        {
            "txn_id": ["T1", "T1", "T2"],
            "date": ["04-09-2024", "04-09-2024", "05-09-2024"],
            "merchant": ["Amazon", "Amazon", "Ola"],
            "amount": ["100", "100", "200"],
            "currency": ["INR", "INR", "INR"],
            "status": ["SUCCESS", "SUCCESS", "FAILED"],
            "category": ["Shopping", "Shopping", "Transport"],
            "account_id": ["ACC001", "ACC001", "ACC002"],
            "notes": ["", "", ""],
        }
    )
    clean, report = cleaning.normalize(df)
    assert report.duplicates_removed == 1
    assert len(clean) == 2


def test_blank_txn_id_rows_are_kept():
    # Two rows with blank txn_id but otherwise different must both survive.
    df = pd.DataFrame(
        {
            "txn_id": ["", ""],
            "date": ["04-09-2024", "05-09-2024"],
            "merchant": ["Amazon", "Ola"],
            "amount": ["100", "200"],
            "currency": ["INR", "INR"],
            "status": ["SUCCESS", "FAILED"],
            "category": ["Shopping", "Transport"],
            "account_id": ["ACC001", "ACC002"],
            "notes": ["", ""],
        }
    )
    clean, report = cleaning.normalize(df)
    assert len(clean) == 2
    assert report.duplicates_removed == 0


def test_sample_fixture_reconciles():
    text = FIXTURE.read_text()
    df = cleaning.read_csv(text)
    clean, report = cleaning.normalize(df)
    assert report.raw == 95
    assert report.duplicates_removed == 10
    assert report.clean == 85
    assert report.is_consistent()


def test_sample_fixture_keeps_blank_txn_ids():
    text = FIXTURE.read_text()
    df = cleaning.read_csv(text)
    clean, _ = cleaning.normalize(df)
    blank = clean["txn_id"].isna().sum()
    # Four rows had blank txn_id; none collapse against each other (rows differ).
    assert blank == 4
