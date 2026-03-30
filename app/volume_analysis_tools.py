import pandas as pd

def calculate_cvd(trades_df: pd.DataFrame) -> pd.Series:
    """
    Calculates the Cumulative Volume Delta (CVD) from a DataFrame of trades.

    Args:
        trades_df: A DataFrame with columns ['price', 'size', 'side'].

    Returns:
        A pandas Series representing the CVD over time.
    """
    if trades_df.empty:
        return pd.Series(dtype=float)

    # Calculate delta for each trade
    trades_df['delta'] = trades_df.apply(
        lambda row: row['size'] if row['side'] == 'Buy' else -row['size'],
        axis=1
    )

    # Calculate cumulative sum of deltas
    cvd_series = trades_df['delta'].cumsum()
    
    return cvd_series
