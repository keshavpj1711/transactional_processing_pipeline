"""Anomaly detection.

Pure functions over a cleaned DataFrame. Two rules from the assignment:

  1. Statistical outlier: an amount greater than three times the median amount
     for that account.
  2. Currency mismatch: a USD transaction at a merchant that only operates
     domestically (Swiggy, Ola, IRCTC).

The median is computed per account in memory because the data is already a
DataFrame at this stage; at large scale this moves to a SQL window function.
"""

import pandas as pd

# Merchants that only transact domestically, so a USD charge is suspicious.
DOMESTIC_ONLY_MERCHANTS = {"swiggy", "ola", "irctc"}

OUTLIER_MULTIPLIER = 3.0


def _outlier_reason(amount: float, median: float) -> str:
    return f"Amount {amount:.2f} exceeds 3x account median ({median:.2f})"


def detect(df: pd.DataFrame) -> pd.DataFrame:
    """Return the DataFrame with ``is_anomaly`` and ``anomaly_reason`` columns.

    A row can trigger both rules; reasons are joined so nothing is hidden.
    """
    df = df.copy()
    reasons: list[list[str]] = [[] for _ in range(len(df))]

    # Rule 1: per-account 3x median outliers.
    if len(df) and df["amount"].notna().any():
        medians = df.groupby("account_id")["amount"].transform("median")
        for pos, (amount, median) in enumerate(zip(df["amount"], medians)):
            if pd.notna(amount) and pd.notna(median) and amount > OUTLIER_MULTIPLIER * median:
                reasons[pos].append(_outlier_reason(amount, median))

    # Rule 2: USD at a domestic-only merchant.
    for pos, (currency, merchant) in enumerate(zip(df["currency"], df["merchant"])):
        if (
            isinstance(currency, str)
            and currency.upper() == "USD"
            and isinstance(merchant, str)
            and merchant.strip().lower() in DOMESTIC_ONLY_MERCHANTS
        ):
            reasons[pos].append(f"USD currency at domestic-only merchant ({merchant})")

    df["anomaly_reason"] = ["; ".join(r) if r else None for r in reasons]
    df["is_anomaly"] = df["anomaly_reason"].notna()
    return df
