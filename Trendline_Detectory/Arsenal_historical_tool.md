# Arsenal Historical Data Tool - Design Plan

## Overview
This tool will extract historical market data that the Arsenal system uses to make trading decisions, allowing for backtesting and analysis of market conditions during winning vs losing trades.

## Data Sources Identified from Arsenal System

### 1. Binance API Endpoints
- **K-line/Candle Data**: `https://api.binance.com/api/v3/klines`
  - Parameters: symbol, interval (5m), limit
  - Returns: open, high, low, close, volume, timestamp

### 2. Binance Futures Endpoints (via python-binance library)
- **Open Interest**: `client.futures_open_interest(symbol)`
- **Funding Rate**: `client.futures_funding_rate(symbol)`
- **Historical Open Interest**: `client.futures_open_interest_hist(symbol, period, limit)`
- **Taker Buy/Sell Ratio**: `client.futures_taker_longshort_ratio(symbol, period, limit)`
- **Global Long/Short Account Ratio**: `client.futures_global_longshort_ratio(symbol, period, limit)`
- **Top Trader Long/Short Account Ratio**: `client.futures_top_longshort_account_ratio(symbol, period, limit)`
- **Ticker Data**: `client.get_ticker(symbol)` (for 24h volume)

### 3. Helios Server Data
- **Helios Context**: `http://localhost:8009/api/v1/helios/context`
  - Contains: btc_trend, sentiment, gls_score, current_price, trend_strength, etc.

### 4. Internal Arsenal Calculations
- **Fair Value Gaps** (FVGs)
- **Order Blocks** (OBs)
- **Liquidity Sweeps**
- **Range Trap Analysis**
- **Volume Profile Analysis**
- **Swing Highs/Lows**
- **Trend Analysis**
- **Candle Patterns**
- **Structural Integrity Score**
- **Confluence Score**

## Tool Architecture

### 1. Data Fetching Module
- **HistoricalDataManager**: Fetches all market data for specified time range
- **Data Format**: 5-minute intervals for all symbols

### 2. Data Storage Module
- **Format**: JSON or CSV (depending on complexity)
- **Structure**: Time-series data with all market indicators
- **File Naming**: `{symbol}_{timeframe}_{start_date}_{end_date}.{json|csv}`

### 3. Data Processing Module
- **MarketFeaturesExtractor**: Extracts all features that Arsenal uses
- **IndexCalculators**: LCI, GLS and other custom indices
- **PatternDetectors**: FVGs, Order Blocks, etc.

### 4. Trade Matching Module
- **TradeHistorian**: Matches historical data with actual trade results
- **CorrelationAnalyzer**: Finds patterns between market conditions and trade outcomes

## Implementation Plan

### Phase 1: Data Fetching
1. Create `HistoricalDataFetcher` class
2. Implement functions for each data source
3. Handle rate limiting and retries
4. Fetch data for all symbols in 5m timeframe

### Phase 2: Data Storage
1. Design JSON structure for storing all market data
2. Create functions to save data to files
3. Implement efficient data serialization

### Phase 3: Market Analysis Features
1. Replicate Arsenal's internal calculations
2. Implement FVG detection
3. Implement Order Block detection
4. Implement Liquidity Sweep detection
5. Implement all other Arsenal features

### Phase 4: Trade Matching
1. Load trade PnL data from the file
2. Align trade timestamps with historical data
3. Extract market features for each trade moment
4. Categorize trades as win/loss by timestamp

### Phase 5: Analysis Engine
1. Compare market conditions during wins vs losses
2. Identify patterns in indicators
3. Generate reports on profitable vs unprofitable conditions
4. Create visualizations

## Data Schema for Historical Storage

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "5m",
  "data": [
    {
      "timestamp": "2025-11-04T21:12:00Z",
      "candle": {
        "open": 60000.0,
        "high": 60100.0,
        "low": 59900.0,
        "close": 60050.0,
        "volume": 100.5
      },
      "market_indicators": {
        "open_interest": 50000.0,
        "funding_rate": 0.0001,
        "taker_buy_sell_ratio": 1.2,
        "global_long_short_ratio": 0.8,
        "top_trader_long_short_ratio": 0.75,
        "lci_score": 0.45,
        "gls_score": 0.32,
        "correlation_with_btc": 0.87,
        "taker_ratio": 0.65,
        "taker_ratio_ma": 0.58,
        "symbol_24h_volume": 150000000.0
      },
      "arsenal_features": {
        "current_price": 60050.0,
        "trend_direction": "uptrend",
        "trend_strength": 0.75,
        "swing_highs_count": 3,
        "swing_lows_count": 2,
        "fvg_count": 1,
        "order_block_count": 2,
        "liquidity_sweep_count": 0,
        "confluence_score": 5,
        "structural_integrity_score": 75,
        "range_trap_active": false,
        "stop_hunt_probability": 0.1,
        "volume_profile_poc": 59950.0,
        "hvn_count": 3
      },
      "trade_info": {
        "has_trade": true,
        "trade_result": "Win", // or "Loss"
        "pnl": 0.65,
        "trade_direction": "Long",
        "entry_price": 60040.0,
        "exit_price": 60200.0
      }
    }
  ]
}
```

## Key Features to Extract

### 1. Price-Based Features
- Open, High, Low, Close prices
- Price momentum and direction
- Volatility measures
- ATR (Average True Range)

### 2. Volume-Based Features
- Trading volume
- Taker/maker ratios
- Volume spikes
- 24h volume

### 3. Sentiment Features
- Long/Short ratios (global and top trader)
- Taker Buy/Sell ratios
- Open Interest changes
- Funding rates

### 4. Technical Features
- Fair Value Gaps
- Order Blocks
- Liquidity Sweeps
- Swing Highs/Lows
- Trend direction and strength
- RSI, MACD (if calculated by Arsenal)
- Support/Resistance levels

### 5. Composite Indices
- Local Crowd Index (LCI)
- Global Leverage Stress (GLS)
- Confluence Score
- Structural Integrity Score

## Matching Algorithm

1. **Time Alignment**: Match trade execution time with historical data timestamp
2. **Feature Extraction**: Extract all market features at that specific time
3. **Classification**: Label each data point as Win/Loss based on trade outcome
4. **Pattern Recognition**: Identify conditions that correlate with wins/losses

## Expected Output Reports

### 1. Market Condition Analysis
- Average LCI during wins vs losses
- Average GLS during wins vs losses
- Volume patterns during wins vs losses
- Sentiment patterns during wins vs losses

### 2. Feature Importance
- Which indicators most strongly correlate with wins/losses
- Conditions that consistently lead to losses
- Market setups that consistently lead to wins

### 3. Symbol-Specific Insights
- Performance differences across symbols
- Symbol-specific patterns
- Optimal conditions per symbol

## Timeline
- **Phase 1**: 2-3 days
- **Phase 2**: 1-2 days
- **Phase 3**: 3-4 days
- **Phase 4**: 2 days
- **Phase 5**: 2-3 days
- **Total**: 10-14 days

This comprehensive tool will allow us to analyze exactly what market conditions led to profitable vs unprofitable trades and optimize the Arsenal system accordingly.