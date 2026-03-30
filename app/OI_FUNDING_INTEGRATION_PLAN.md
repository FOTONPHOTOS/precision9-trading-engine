# Arsenal: OI & Funding Rate Integration Plan

## 1. Executive Summary

This document outlines the surgical integration of Open Interest (OI) and Funding Rate (FR) data into the Arsenal ecosystem. We will build two core metrics—a **Local Crowd Index (LCI)** for the traded symbol and a **Global Leverage Stress (GLS)** index from BTC—and inject them at key decision points to enhance risk management, improve entry precision, and reduce catastrophic losses from liquidations and stop hunts.

---

## 2. Core Principle: Separation of Responsibilities

OI and Funding data will be treated as *regime and crowd signals*, not as raw entry triggers. The integration will respect a clear separation of responsibilities:

- **Global Leverage Stress (GLS):** A measure of systemic risk in the entire market, derived from BTC. It tells all bots how cautiously they should behave.
- **Local Crowd Index (LCI):** A measure of crowd positioning and sentiment for a *specific symbol*. It is used to fade crowded trades and confirm liquidations.
- **Arsenal Brain:** Remains the primary strategic decision-maker, but now uses LCI and GLS as critical inputs in its chain-of-thought.
- **Horus & Aegis:** Act as final quality and safety gates, using the new indices to adjust their aggressiveness in real-time.

---

## 3. New Core Components

Two new components will be created, likely within a new `oi_funding_engine.py` module.

### 3.1. OI/Funding Data Fetcher
- A dedicated class responsible for fetching OI and Funding Rate data from the exchange.
- It will include caching logic (e.g., 5-minute TTL) to avoid excessive API calls.
- It will handle data normalization, such as calculating the 24-hour average funding rate.

### 3.2. Local Crowd Index (LCI) Calculator
- A function that computes the LCI for a given symbol based on a smoothed formula of OI change, funding rate skew, and CVD alignment.
- `LCI = sigmoid(w1 * ΔOI_pct_norm + w2 * FR_norm + w3 * CVD_alignment)`
- This index (0 to 1) quantifies how crowded or over-leveraged a specific symbol is.

### 3.3. Global Leverage Stress (GLS) Calculator
- A function that computes the GLS (0 to 1) using only BTC data.
- `GLS = normalize(alpha * ΔOI_BTC + beta * |FR_BTC| + gamma * OI_BTC_vs_Avg)`
- This index quantifies the overall systemic risk in the market.

---

## 4. Integration Plan by System Component

### Phase 1: Data Layer & Helios Integration
1.  **Create `oi_funding_engine.py`:**
    -   Implement the data fetcher class.
    -   Implement the `compute_lci` and `compute_gls` functions with placeholder data initially.
2.  **Upgrade Helios Server (`helios_server.py`):**
    -   Integrate the `compute_gls` function.
    -   In its main analysis loop, fetch BTC OI/FR data and calculate the GLS score.
    -   Add the `gls_score` and its timestamp to the `/api/v1/helios/context` API response.

### Phase 2: Brain & Detector Refactoring
1.  **Refactor `liquidity_sweep_detector.py`:**
    -   Modify `detect_stop_hunt_mode` to accept the `lci_score` as a new parameter.
    -   Instead of a binary `is_stop_hunt_mode` flag, it will now output a `stop_hunt_probability` (0.0 to 1.0).
    -   The `lci_score` will act as a multiplier, increasing the probability if the crowd is heavily positioned against the direction of the sweep.
2.  **Refactor `trend_continuation_brain.py`:**
    -   Add `lci_score` and `gls_score` as new parameters to the `analyze` method.
    -   **Replace Hard Block:** Remove the hard block for `is_stop_hunt_mode`. Replace it with a probabilistic check: `if stop_hunt_probability > 0.8: ...`.
    -   **Add LCI Confluence:** Use the LCI score as a powerful confluence factor. Increase confidence for trades that "fade the crowd" (e.g., going LONG when LCI shows extreme short positioning).
    -   **Add Extreme Funding Blocker:** Implement a new critical blocker that rejects trades if the absolute funding rate is >2.5x its 24-hour average.
    -   **Add Dynamic Position Sizing:** Adjust the final `position_size_multiplier` based on LCI and GLS, reducing size when either index is high.
3.  **Refactor `live_arsenal_horus_integrated.py`:**
    -   Integrate the new `oi_funding_engine`.
    -   In the main analysis cycle:
        -   Fetch the `gls_score` from the Helios context.
        -   Calculate the `lci_score` for the current symbol.
        -   Pass `lci_score` into the `detect_stop_hunt_mode` function.
        -   Pass both `lci_score` and `gls_score` into the `tc_brain.analyze` function.

### Phase 3: Entry & Post-Entry Refactoring
1.  **Refactor `horus_precision_entry_system.py`:**
    -   Pass the `gls_score` into the Horus confirmation step.
    -   If `gls_score` is high, Horus will require a stronger order flow confirmation signal before returning `True`.
2.  **Refactor Aegis (`eyes_of_horus/trade_manager.py`):**
    -   This is a future enhancement. The plan is to modify Aegis to accept the LCI and GLS scores with the initial trade signal.
    -   Aegis will then monitor OI/FR data in real-time for the open position. If it detects a dangerous shift (e.g., OI dropping rapidly against the position), it can take protective action like tightening the stop-loss or partially closing the trade.

---

## 5. Backtesting & Validation Strategy

Before deploying live, the following metrics will be analyzed to validate the effectiveness of the integration:

-   **Drawdown Reduction:** Compare the average/max drawdown per trade before and after the OI/FR integration.
-   **Catastrophic Loss Elimination:** Verify that the new logic prevents trades during major, known liquidation events from the past.
-   **Profit Factor Change:** Ensure that while some winning trades may be filtered out, the overall profitability ratio improves due to fewer, larger losses.
-   **Signal Rejection Rate:** Monitor the percentage of trades blocked by the new LCI/GLS logic to ensure it is not overly restrictive.

This plan provides a clear, surgical path to integrating sophisticated new data sources while respecting the existing architecture and minimizing risk.
