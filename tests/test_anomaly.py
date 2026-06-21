import pandas as pd

from app.pipeline import anomaly


def _df(rows):
    cols = ["txn_id", "date", "merchant", "amount", "currency", "status", "category", "account_id", "notes"]
    return pd.DataFrame(rows, columns=cols)


def test_outlier_above_3x_account_median_is_flagged():
    df = _df(
        [
            ["T1", "2024-01-01", "Amazon", 100.0, "INR", "SUCCESS", "Shopping", "ACC001", None],
            ["T2", "2024-01-02", "Amazon", 100.0, "INR", "SUCCESS", "Shopping", "ACC001", None],
            ["T3", "2024-01-03", "Amazon", 100.0, "INR", "SUCCESS", "Shopping", "ACC001", None],
            ["T4", "2024-01-04", "Amazon", 5000.0, "INR", "SUCCESS", "Shopping", "ACC001", None],
        ]
    )
    out = anomaly.detect(df)
    flagged = out[out["is_anomaly"]]
    assert list(flagged["txn_id"]) == ["T4"]
    assert "median" in flagged.iloc[0]["anomaly_reason"]


def test_median_is_per_account():
    # A large amount that is normal for its own account is not flagged.
    df = _df(
        [
            ["T1", "2024-01-01", "Amazon", 100.0, "INR", "SUCCESS", "Shopping", "ACC001", None],
            ["T2", "2024-01-02", "Amazon", 100.0, "INR", "SUCCESS", "Shopping", "ACC001", None],
            ["T3", "2024-01-03", "Amazon", 9000.0, "INR", "SUCCESS", "Shopping", "ACC002", None],
            ["T4", "2024-01-04", "Amazon", 9000.0, "INR", "SUCCESS", "Shopping", "ACC002", None],
        ]
    )
    out = anomaly.detect(df)
    assert not out["is_anomaly"].any()


def test_usd_at_domestic_merchant_is_flagged():
    df = _df(
        [
            ["T1", "2024-01-01", "Swiggy", 100.0, "USD", "SUCCESS", "Food", "ACC001", None],
            ["T2", "2024-01-02", "Ola", 100.0, "USD", "SUCCESS", "Transport", "ACC001", None],
            ["T3", "2024-01-03", "IRCTC", 100.0, "USD", "SUCCESS", "Travel", "ACC001", None],
            ["T4", "2024-01-04", "Amazon", 100.0, "USD", "SUCCESS", "Shopping", "ACC001", None],
        ]
    )
    out = anomaly.detect(df)
    flagged = set(out[out["is_anomaly"]]["txn_id"])
    assert flagged == {"T1", "T2", "T3"}
    assert "domestic-only" in out[out["txn_id"] == "T1"].iloc[0]["anomaly_reason"]


def test_both_rules_combine_in_reason():
    df = _df(
        [
            ["T1", "2024-01-01", "Swiggy", 100.0, "INR", "SUCCESS", "Food", "ACC001", None],
            ["T2", "2024-01-02", "Swiggy", 100.0, "INR", "SUCCESS", "Food", "ACC001", None],
            ["T3", "2024-01-03", "Swiggy", 5000.0, "USD", "SUCCESS", "Food", "ACC001", None],
        ]
    )
    out = anomaly.detect(df)
    reason = out[out["txn_id"] == "T3"].iloc[0]["anomaly_reason"]
    assert "median" in reason and "domestic-only" in reason


def test_usd_at_non_domestic_merchant_not_flagged():
    df = _df(
        [
            ["T1", "2024-01-01", "Amazon", 100.0, "USD", "SUCCESS", "Shopping", "ACC001", None],
            ["T2", "2024-01-02", "Amazon", 100.0, "USD", "SUCCESS", "Shopping", "ACC001", None],
        ]
    )
    out = anomaly.detect(df)
    assert not out["is_anomaly"].any()
