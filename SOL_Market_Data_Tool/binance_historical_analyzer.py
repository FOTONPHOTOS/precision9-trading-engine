#!/usr/bin/env python3
"""
Binance Historical Data Analyzer for SOL
=========================================
Analyzes historical Binance futures data to identify patterns,
compare with recent tracking, and generate trading insights.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import matplotlib.pyplot as plt
try:
    import seaborn as sns
    sns.set_style("whitegrid")
except ImportError:
    pass  # Seaborn is optional
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class BinanceHistoricalAnalyzer:
    """Analyzes Binance historical futures data for SOL"""
    
    def __init__(self):
        """Initialize the analyzer"""
        self.data_files = {
            'SOLBUSD_day': Path(r"G:\python files\precision9\claude\SOLBUSD_Binance_futures_UM_day.csv"),
            'SOLBUSD_hour': Path(r"G:\python files\precision9\claude\SOLBUSD_Binance_futures_UM_hour.csv"),
            'SOLUSDT_day': Path(r"G:\python files\precision9\claude\SOLUSDT_Binance_futures_UM_day.csv"),
            'SOLUSDT_hour': Path(r"G:\python files\precision9\claude\SOLUSDT_Binance_futures_UM_hour.csv")
        }
        
        self.data = {}
        self.analysis_results = {}
        
        # Recent tracking data (5 hours ago)
        self.recent_tracking = {
            'duration_hours': 5.33,
            'start_price': 176.41,
            'end_price': 180.16,
            'price_change': 3.75,
            'price_change_pct': 2.13,
            'cvd_start': -3.74,
            'cvd_end': 103458.79,  # Likely corrupted
            'buy_sell_ratio': 1.472,
            'volatility': 0.88,
            'price_range': 5.81,
            'low': 175.88,
            'high': 181.69,
            'max_drawdown': -1.19,
            'correlation_cvd_price': 0.643,
            'accumulation_pct': 30.7,
            'distribution_pct': 21.1,
            'best_hour_utc': 4,
            'peak_volume': 7238,
            'quiet_volume': 697
        }
    
    def load_data(self):
        """Load all CSV files"""
        print("="*70)
        print("LOADING BINANCE HISTORICAL DATA")
        print("="*70)
        
        for name, filepath in self.data_files.items():
            try:
                if filepath.exists():
                    df = pd.read_csv(filepath)
                    
                    # Standardize column names
                    df.columns = [col.strip().lower() for col in df.columns]
                    
                    # Parse datetime
                    if 'date' in df.columns:
                        df['datetime'] = pd.to_datetime(df['date'])
                    elif 'open time' in df.columns:
                        df['datetime'] = pd.to_datetime(df['open time'])
                    elif 'time' in df.columns:
                        df['datetime'] = pd.to_datetime(df['time'])
                    
                    # Ensure numeric columns
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    # Sort by date
                    df = df.sort_values('datetime')
                    
                    # Add calculated columns
                    df['price_change'] = df['close'] - df['open']
                    df['price_change_pct'] = (df['price_change'] / df['open']) * 100
                    df['range'] = df['high'] - df['low']
                    df['range_pct'] = (df['range'] / df['open']) * 100
                    
                    # Calculate returns
                    df['returns'] = df['close'].pct_change()
                    
                    # Calculate volatility (20-period rolling)
                    df['volatility'] = df['returns'].rolling(20).std() * 100
                    
                    # Volume analysis
                    df['volume_ma'] = df['volume'].rolling(20).mean()
                    df['volume_ratio'] = df['volume'] / df['volume_ma']
                    
                    self.data[name] = df
                    print(f" Loaded {name}: {len(df)} records from {df['datetime'].min()} to {df['datetime'].max()}")
                else:
                    print(f" File not found: {filepath}")
            except Exception as e:
                print(f" Error loading {name}: {e}")
        
        print()
    
    def analyze_price_patterns(self):
        """Analyze historical price patterns"""
        print("="*70)
        print("PRICE PATTERN ANALYSIS")
        print("="*70)
        
        results = {}
        
        for name, df in self.data.items():
            if df is None or df.empty:
                continue
            
            print(f"\n{name.upper()} Analysis:")
            print("-"*40)
            
            # Basic statistics
            stats_dict = {
                'mean_price': df['close'].mean(),
                'median_price': df['close'].median(),
                'std_price': df['close'].std(),
                'min_price': df['close'].min(),
                'max_price': df['close'].max(),
                'total_range': df['close'].max() - df['close'].min(),
                'avg_daily_range': df['range'].mean(),
                'avg_daily_range_pct': df['range_pct'].mean(),
                'avg_returns': df['returns'].mean() * 100,
                'volatility': df['returns'].std() * 100,
                'skewness': df['returns'].skew(),
                'kurtosis': df['returns'].kurtosis()
            }
            
            print(f"  Average Price: ${stats_dict['mean_price']:.2f}")
            print(f"  Price Range: ${stats_dict['min_price']:.2f} - ${stats_dict['max_price']:.2f}")
            print(f"  Average Daily Range: {stats_dict['avg_daily_range_pct']:.2f}%")
            print(f"  Historical Volatility: {stats_dict['volatility']:.2f}%")
            print(f"  Skewness: {stats_dict['skewness']:.3f} ({'Right' if stats_dict['skewness'] > 0 else 'Left'} tail)")
            print(f"  Kurtosis: {stats_dict['kurtosis']:.3f} ({'Fat' if stats_dict['kurtosis'] > 3 else 'Thin'} tails)")
            
            # Trend analysis
            recent_30 = df.tail(30) if len(df) > 30 else df
            recent_7 = df.tail(7) if len(df) > 7 else df
            
            trend_30d = (recent_30['close'].iloc[-1] - recent_30['close'].iloc[0]) / recent_30['close'].iloc[0] * 100
            trend_7d = (recent_7['close'].iloc[-1] - recent_7['close'].iloc[0]) / recent_7['close'].iloc[0] * 100
            
            print(f"\n  Recent Trends:")
            print(f"    30-day: {trend_30d:+.2f}%")
            print(f"    7-day: {trend_7d:+.2f}%")
            
            # Identify similar 5-hour periods (for hourly data)
            if 'hour' in name:
                similar_periods = self._find_similar_periods(df, 5)
                stats_dict['similar_5h_periods'] = similar_periods
                
                if similar_periods:
                    print(f"\n  Similar 5-hour Periods to Recent Tracking:")
                    print(f"    Found: {len(similar_periods)} similar periods")
                    print(f"    Average Next Move: {np.mean([p['next_move'] for p in similar_periods]):.2f}%")
                    print(f"    Win Rate: {np.mean([1 if p['next_move'] > 0 else 0 for p in similar_periods])*100:.1f}%")
            
            results[name] = stats_dict
        
        self.analysis_results['price_patterns'] = results
        return results
    
    def _find_similar_periods(self, df, hours=5):
        """Find historical periods similar to recent tracking"""
        if len(df) < hours + 1:
            return []
        
        similar_periods = []
        target_change = self.recent_tracking['price_change_pct']
        target_volatility = self.recent_tracking['volatility']
        
        # Slide through history
        for i in range(len(df) - hours - 24):  # Leave room for next 24h
            period = df.iloc[i:i+hours]
            
            # Calculate period metrics
            period_change = ((period['close'].iloc[-1] - period['close'].iloc[0]) / period['close'].iloc[0]) * 100
            period_volatility = period['returns'].std() * 100 if 'returns' in period.columns else 0
            period_range = ((period['high'].max() - period['low'].min()) / period['close'].iloc[0]) * 100
            
            # Check similarity (within 30% of target metrics)
            if (abs(period_change - target_change) < target_change * 0.3 and
                abs(period_volatility - target_volatility) < target_volatility * 0.3):
                
                # Get next 24h performance
                next_period = df.iloc[i+hours:min(i+hours+24, len(df))]
                if not next_period.empty:
                    next_move = ((next_period['close'].iloc[-1] - period['close'].iloc[-1]) / period['close'].iloc[-1]) * 100
                    
                    similar_periods.append({
                        'start_date': period['datetime'].iloc[0],
                        'end_date': period['datetime'].iloc[-1],
                        'period_change': period_change,
                        'period_volatility': period_volatility,
                        'period_range': period_range,
                        'next_move': next_move,
                        'next_high': ((next_period['high'].max() - period['close'].iloc[-1]) / period['close'].iloc[-1]) * 100,
                        'next_low': ((next_period['low'].min() - period['close'].iloc[-1]) / period['close'].iloc[-1]) * 100
                    })
        
        return similar_periods
    
    def analyze_volume_patterns(self):
        """Analyze volume patterns and relationships"""
        print("\n" + "="*70)
        print("VOLUME PATTERN ANALYSIS")
        print("="*70)
        
        results = {}
        
        for name, df in self.data.items():
            if df is None or df.empty or 'volume' not in df.columns:
                continue
            
            print(f"\n{name.upper()} Volume Analysis:")
            print("-"*40)
            
            # Volume statistics
            vol_stats = {
                'avg_volume': df['volume'].mean(),
                'median_volume': df['volume'].median(),
                'max_volume': df['volume'].max(),
                'min_volume': df['volume'].min(),
                'volume_std': df['volume'].std()
            }
            
            # Volume-price correlation
            vol_price_corr = df['volume'].corr(df['price_change'].abs()) if 'price_change' in df.columns else 0
            
            # Identify high volume days
            high_vol_threshold = df['volume'].quantile(0.9)
            high_vol_days = df[df['volume'] > high_vol_threshold]
            
            # Performance after high volume
            high_vol_returns = []
            for idx in high_vol_days.index:
                if idx + 1 < len(df):
                    next_return = df.loc[idx + 1, 'returns'] if 'returns' in df.columns else 0
                    high_vol_returns.append(next_return)
            
            avg_return_after_high_vol = np.mean(high_vol_returns) * 100 if high_vol_returns else 0
            
            print(f"  Average Volume: {vol_stats['avg_volume']:,.0f}")
            print(f"  Volume-Movement Correlation: {vol_price_corr:.3f}")
            print(f"  High Volume Days: {len(high_vol_days)} ({len(high_vol_days)/len(df)*100:.1f}%)")
            print(f"  Avg Return After High Volume: {avg_return_after_high_vol:+.2f}%")
            
            # Compare with recent tracking
            if 'hour' in name:
                volume_multiplier = self.recent_tracking['peak_volume'] / self.recent_tracking['quiet_volume']
                print(f"\n  Recent Tracking Comparison:")
                print(f"    Peak/Quiet Ratio: {volume_multiplier:.1f}x")
                print(f"    Historical Avg Ratio: {df['volume'].max() / df['volume'].min():.1f}x")
            
            vol_stats['vol_price_correlation'] = vol_price_corr
            vol_stats['high_volume_days'] = len(high_vol_days)
            vol_stats['avg_return_after_high_vol'] = avg_return_after_high_vol
            
            results[name] = vol_stats
        
        self.analysis_results['volume_patterns'] = results
        return results
    
    def analyze_momentum_cycles(self):
        """Analyze momentum and cyclical patterns"""
        print("\n" + "="*70)
        print("MOMENTUM & CYCLE ANALYSIS")
        print("="*70)
        
        results = {}
        
        for name, df in self.data.items():
            if df is None or df.empty:
                continue
            
            print(f"\n{name.upper()} Momentum Analysis:")
            print("-"*40)
            
            # Calculate momentum indicators
            df['momentum_5'] = df['close'] - df['close'].shift(5)
            df['momentum_10'] = df['close'] - df['close'].shift(10)
            df['momentum_20'] = df['close'] - df['close'].shift(20)
            
            # RSI calculation
            def calculate_rsi(prices, period=14):
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                return rsi
            
            df['rsi'] = calculate_rsi(df['close'])
            
            # Identify momentum regimes
            strong_bullish = df[df['momentum_5'] > df['momentum_5'].quantile(0.8)]
            strong_bearish = df[df['momentum_5'] < df['momentum_5'].quantile(0.2)]
            
            # Average returns in different momentum regimes
            bullish_next_return = 0
            bearish_next_return = 0
            
            if len(strong_bullish) > 0:
                bullish_returns = []
                for idx in strong_bullish.index:
                    if idx + 1 < len(df):
                        bullish_returns.append(df.loc[idx + 1, 'returns'])
                bullish_next_return = np.mean(bullish_returns) * 100 if bullish_returns else 0
            
            if len(strong_bearish) > 0:
                bearish_returns = []
                for idx in strong_bearish.index:
                    if idx + 1 < len(df):
                        bearish_returns.append(df.loc[idx + 1, 'returns'])
                bearish_next_return = np.mean(bearish_returns) * 100 if bearish_returns else 0
            
            # RSI extremes
            oversold = df[df['rsi'] < 30] if 'rsi' in df.columns else pd.DataFrame()
            overbought = df[df['rsi'] > 70] if 'rsi' in df.columns else pd.DataFrame()
            
            print(f"  Strong Bullish Periods: {len(strong_bullish)} ({len(strong_bullish)/len(df)*100:.1f}%)")
            print(f"  Strong Bearish Periods: {len(strong_bearish)} ({len(strong_bearish)/len(df)*100:.1f}%)")
            print(f"  Avg Return After Bullish: {bullish_next_return:+.2f}%")
            print(f"  Avg Return After Bearish: {bearish_next_return:+.2f}%")
            
            if not oversold.empty or not overbought.empty:
                print(f"\n  RSI Extremes:")
                print(f"    Oversold (<30): {len(oversold)} times")
                print(f"    Overbought (>70): {len(overbought)} times")
            
            # Cycle detection (simple approach using FFT for daily data)
            if 'day' in name and len(df) > 100:
                from scipy.fft import fft, fftfreq
                
                # Detrend the data
                detrended = df['close'] - df['close'].rolling(50).mean()
                detrended = detrended.dropna()
                
                # Apply FFT
                yf = fft(detrended.values)
                xf = fftfreq(len(detrended), 1)
                
                # Find dominant frequencies
                power = np.abs(yf)
                dominant_freq_idx = np.argsort(power)[-5:]  # Top 5 frequencies
                dominant_periods = [1/abs(xf[idx]) for idx in dominant_freq_idx if xf[idx] != 0]
                dominant_periods = [p for p in dominant_periods if p < 100 and p > 2]  # Filter reasonable periods
                
                if dominant_periods:
                    print(f"\n  Detected Cycles (days): {[f'{p:.1f}' for p in sorted(dominant_periods)]}")
            
            momentum_stats = {
                'bullish_periods': len(strong_bullish),
                'bearish_periods': len(strong_bearish),
                'bullish_next_return': bullish_next_return,
                'bearish_next_return': bearish_next_return,
                'oversold_count': len(oversold),
                'overbought_count': len(overbought)
            }
            
            results[name] = momentum_stats
        
        self.analysis_results['momentum_cycles'] = results
        return results
    
    def analyze_optimal_trading_times(self):
        """Analyze optimal trading times for hourly data"""
        print("\n" + "="*70)
        print("OPTIMAL TRADING TIME ANALYSIS")
        print("="*70)
        
        results = {}
        
        for name, df in self.data.items():
            if 'hour' not in name or df is None or df.empty:
                continue
            
            print(f"\n{name.upper()} Hourly Pattern Analysis:")
            print("-"*40)
            
            # Extract hour from datetime
            df['hour'] = df['datetime'].dt.hour
            
            # Group by hour
            hourly_stats = df.groupby('hour').agg({
                'returns': ['mean', 'std', 'count'],
                'volume': 'mean',
                'range_pct': 'mean'
            })
            
            # Flatten column names
            hourly_stats.columns = ['_'.join(col).strip() for col in hourly_stats.columns]
            
            # Find best and worst hours
            best_hours = hourly_stats.nlargest(3, 'returns_mean')
            worst_hours = hourly_stats.nsmallest(3, 'returns_mean')
            most_volatile = hourly_stats.nlargest(3, 'returns_std')
            highest_volume = hourly_stats.nlargest(3, 'volume_mean')
            
            print(f"  Best Hours (UTC):")
            for hour in best_hours.index:
                avg_return = best_hours.loc[hour, 'returns_mean'] * 100
                print(f"    {hour:02d}:00 - Avg Return: {avg_return:+.3f}%")
            
            print(f"\n  Most Volatile Hours (UTC):")
            for hour in most_volatile.index:
                volatility = most_volatile.loc[hour, 'returns_std'] * 100
                print(f"    {hour:02d}:00 - Volatility: {volatility:.3f}%")
            
            print(f"\n  Highest Volume Hours (UTC):")
            for hour in highest_volume.index:
                volume = highest_volume.loc[hour, 'volume_mean']
                print(f"    {hour:02d}:00 - Avg Volume: {volume:,.0f}")
            
            # Compare with recent tracking
            if self.recent_tracking['best_hour_utc'] in hourly_stats.index:
                tracked_hour = self.recent_tracking['best_hour_utc']
                print(f"\n  Recent Tracking Best Hour ({tracked_hour:02d}:00 UTC):")
                print(f"    Historical Avg Return: {hourly_stats.loc[tracked_hour, 'returns_mean']*100:+.3f}%")
                print(f"    Historical Volatility: {hourly_stats.loc[tracked_hour, 'returns_std']*100:.3f}%")
            
            results[name] = {
                'best_hours': best_hours.index.tolist(),
                'worst_hours': worst_hours.index.tolist(),
                'most_volatile_hours': most_volatile.index.tolist(),
                'highest_volume_hours': highest_volume.index.tolist(),
                'hourly_stats': hourly_stats.to_dict()
            }
        
        self.analysis_results['trading_times'] = results
        return results
    
    def compare_with_recent_tracking(self):
        """Compare historical patterns with recent 5-hour tracking"""
        print("\n" + "="*70)
        print("COMPARISON WITH RECENT 5-HOUR TRACKING")
        print("="*70)
        
        print("\nRecent Tracking Summary (5.33 hours):")
        print("-"*40)
        print(f"  Price Change: +${self.recent_tracking['price_change']:.2f} ({self.recent_tracking['price_change_pct']:+.2f}%)")
        print(f"  Volatility: {self.recent_tracking['volatility']:.2f}%")
        print(f"  Buy/Sell Ratio: {self.recent_tracking['buy_sell_ratio']:.3f}")
        print(f"  Price Range: ${self.recent_tracking['price_range']:.2f}")
        print(f"  Max Drawdown: {self.recent_tracking['max_drawdown']:.2f}%")
        
        # Find historical context
        for name, df in self.data.items():
            if 'hour' not in name or df is None or df.empty:
                continue
            
            print(f"\n{name.upper()} Historical Context:")
            print("-"*40)
            
            # Calculate 5-hour rolling metrics
            window = 5
            df['rolling_return_5h'] = df['close'].pct_change(window) * 100
            df['rolling_volatility_5h'] = df['returns'].rolling(window).std() * 100
            df['rolling_range_5h'] = (df['high'].rolling(window).max() - df['low'].rolling(window).min()) / df['close'] * 100
            
            # Find percentile of recent performance
            recent_return_percentile = stats.percentileofscore(
                df['rolling_return_5h'].dropna(), 
                self.recent_tracking['price_change_pct']
            )
            
            recent_vol_percentile = stats.percentileofscore(
                df['rolling_volatility_5h'].dropna(), 
                self.recent_tracking['volatility']
            )
            
            print(f"  Recent 5h return ({self.recent_tracking['price_change_pct']:+.2f}%) is in {recent_return_percentile:.1f}th percentile")
            print(f"  Recent volatility ({self.recent_tracking['volatility']:.2f}%) is in {recent_vol_percentile:.1f}th percentile")
            
            # Historical statistics for 5-hour periods
            print(f"\n  Historical 5-hour Period Statistics:")
            print(f"    Average Return: {df['rolling_return_5h'].mean():.2f}%")
            print(f"    Median Return: {df['rolling_return_5h'].median():.2f}%")
            print(f"    Standard Deviation: {df['rolling_return_5h'].std():.2f}%")
            print(f"    95th Percentile: {df['rolling_return_5h'].quantile(0.95):.2f}%")
            print(f"    5th Percentile: {df['rolling_return_5h'].quantile(0.05):.2f}%")
            
            # Interpretation
            print(f"\n   INTERPRETATION:")
            if recent_return_percentile > 80:
                print(f"    - Recent performance is EXCEPTIONALLY BULLISH (top 20%)")
                print(f"    - Caution: Potential for mean reversion")
            elif recent_return_percentile > 60:
                print(f"    - Recent performance is ABOVE AVERAGE")
                print(f"    - Momentum may continue if volume supports")
            elif recent_return_percentile < 20:
                print(f"    - Recent performance is WEAK (bottom 20%)")
                print(f"    - Watch for potential bounce or continued weakness")
            else:
                print(f"    - Recent performance is NORMAL")
                print(f"    - No extreme conditions detected")
            
            if recent_vol_percentile < 30:
                print(f"    - Volatility is LOW - Potential for breakout")
            elif recent_vol_percentile > 70:
                print(f"    - Volatility is HIGH - Increased risk")
    
    def generate_trading_recommendations(self):
        """Generate actionable trading recommendations"""
        print("\n" + "="*70)
        print(" TRADING RECOMMENDATIONS")
        print("="*70)
        
        recommendations = {}
        
        # Analyze current market context
        print("\n CURRENT MARKET CONTEXT:")
        print("-"*40)
        
        # Get latest data
        latest_prices = {}
        for name, df in self.data.items():
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                latest_prices[name] = {
                    'close': latest['close'],
                    'date': latest['datetime'],
                    'volume': latest.get('volume', 0)
                }
        
        # Price analysis
        if 'SOLUSDT_day' in latest_prices:
            current_price = latest_prices['SOLUSDT_day']['close']
            print(f"  Current Price Level: ${current_price:.2f}")
            
            # Support/Resistance from historical data
            if 'SOLUSDT_day' in self.data:
                df = self.data['SOLUSDT_day']
                recent_high = df.tail(30)['high'].max()
                recent_low = df.tail(30)['low'].min()
                
                print(f"  30-day Range: ${recent_low:.2f} - ${recent_high:.2f}")
                print(f"  Position in Range: {((current_price - recent_low) / (recent_high - recent_low) * 100):.1f}%")
        
        print("\n TRADING STRATEGY RECOMMENDATIONS:")
        print("-"*40)
        
        # Based on momentum analysis
        if 'momentum_cycles' in self.analysis_results:
            for name, stats in self.analysis_results['momentum_cycles'].items():
                if 'hour' in name:
                    print(f"\n{name.upper()} Strategy:")
                    
                    # Momentum trading
                    if stats['bullish_next_return'] > 0.5:
                        print(f"   MOMENTUM LONG: Strong bullish continuation")
                        print(f"     Expected return after bullish signal: {stats['bullish_next_return']:+.2f}%")
                    
                    if stats['bearish_next_return'] < -0.5:
                        print(f"   MOMENTUM SHORT: Strong bearish continuation")
                        print(f"     Expected return after bearish signal: {stats['bearish_next_return']:+.2f}%")
                    
                    # Mean reversion
                    if stats['oversold_count'] > 0:
                        print(f"   MEAN REVERSION: Watch for oversold bounces")
                        print(f"     Historical oversold occurrences: {stats['oversold_count']}")
        
        # Based on volume patterns
        if 'volume_patterns' in self.analysis_results:
            print("\n VOLUME-BASED SIGNALS:")
            for name, stats in self.analysis_results['volume_patterns'].items():
                if stats['avg_return_after_high_vol'] > 0.5:
                    print(f"   {name}: Trade breakouts on high volume")
                    print(f"     Avg return after high volume: {stats['avg_return_after_high_vol']:+.2f}%")
        
        # Optimal trading times
        if 'trading_times' in self.analysis_results:
            print("\n⏰ OPTIMAL TRADING WINDOWS (UTC):")
            for name, times in self.analysis_results['trading_times'].items():
                if 'hour' in name:
                    print(f"  {name}:")
                    print(f"    Best Hours: {times['best_hours']}")
                    print(f"    Most Volatile: {times['most_volatile_hours']}")
                    print(f"    Highest Volume: {times['highest_volume_hours']}")
        
        # Risk management
        print("\n RISK MANAGEMENT:")
        print("-"*40)
        
        if self.data:
            # Calculate recommended position sizing based on volatility
            for name, df in self.data.items():
                if 'day' in name and not df.empty:
                    recent_volatility = df.tail(20)['returns'].std() * 100
                    recommended_position = 1 / (recent_volatility * 2)  # Kelly-inspired sizing
                    
                    print(f"  {name}:")
                    print(f"    Recent Volatility: {recent_volatility:.2f}%")
                    print(f"    Recommended Position Size: {recommended_position:.2f}x base")
                    print(f"    Suggested Stop Loss: {recent_volatility * 2:.2f}%")
                    print(f"    Suggested Take Profit: {recent_volatility * 3:.2f}%")
        
        # CVD Warning
        print("\n CVD DATA WARNING:")
        print("-"*40)
        print("  Your recent CVD tracking shows anomalous values (103,458)")
        print("  This suggests a calculation error in the collector")
        print("  Recommendations:")
        print("    1. Check CVD calculation logic for overflow/accumulation errors")
        print("    2. Implement CVD reset at session boundaries")
        print("    3. Add validation checks for reasonable CVD ranges")
        
        # Action items
        print("\n ACTION ITEMS:")
        print("-"*40)
        print("  1. Focus on UTC hours 4-5 for highest volume (confirmed by your tracking)")
        print("  2. Current low volatility (0.88%) suggests potential breakout incoming")
        print("  3. Strong buy/sell ratio (1.472) indicates bullish sentiment")
        print("  4. Monitor for continuation above $180 resistance")
        print("  5. Set alerts for volatility expansion above 1.5%")
        
        return recommendations
    
    def visualize_analysis(self):
        """Create visualization plots"""
        print("\n" + "="*70)
        print("GENERATING VISUALIZATIONS")
        print("="*70)
        
        # Create figure with subplots
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        fig.suptitle('SOL Historical Analysis vs Recent Tracking', fontsize=16, y=1.02)
        
        # Plot 1: Price history with recent tracking overlay
        ax = axes[0, 0]
        for name, df in self.data.items():
            if 'day' in name and not df.empty:
                ax.plot(df['datetime'], df['close'], label=name, alpha=0.7)
        
        # Add recent tracking level
        ax.axhline(y=self.recent_tracking['start_price'], color='green', linestyle='--', label='Recent Start', alpha=0.5)
        ax.axhline(y=self.recent_tracking['end_price'], color='red', linestyle='--', label='Recent End', alpha=0.5)
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Price ($)')
        ax.set_title('Historical Price Movement')
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Plot 2: Returns distribution
        ax = axes[0, 1]
        for name, df in self.data.items():
            if 'hour' in name and not df.empty and 'returns' in df.columns:
                returns = df['returns'].dropna() * 100
                ax.hist(returns, bins=50, alpha=0.5, label=name)
        
        # Add recent tracking return
        ax.axvline(x=self.recent_tracking['price_change_pct'], color='red', linestyle='--', 
                  label=f"Recent 5h: {self.recent_tracking['price_change_pct']:.2f}%", linewidth=2)
        
        ax.set_xlabel('Returns (%)')
        ax.set_ylabel('Frequency')
        ax.set_title('Returns Distribution')
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Plot 3: Hourly patterns
        ax = axes[1, 0]
        for name, df in self.data.items():
            if 'hour' in name and not df.empty:
                df['hour'] = df['datetime'].dt.hour
                hourly_returns = df.groupby('hour')['returns'].mean() * 100
                ax.plot(hourly_returns.index, hourly_returns.values, marker='o', label=name, alpha=0.7)
        
        # Highlight recent best hour
        ax.axvline(x=self.recent_tracking['best_hour_utc'], color='red', linestyle='--', 
                  label=f"Recent Best: {self.recent_tracking['best_hour_utc']}:00", alpha=0.5)
        
        ax.set_xlabel('Hour (UTC)')
        ax.set_ylabel('Average Return (%)')
        ax.set_title('Hourly Return Patterns')
        ax.set_xticks(range(0, 24, 2))
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Plot 4: Volume patterns
        ax = axes[1, 1]
        for name, df in self.data.items():
            if 'hour' in name and not df.empty and 'volume' in df.columns:
                df['hour'] = df['datetime'].dt.hour
                hourly_volume = df.groupby('hour')['volume'].mean()
                ax.plot(hourly_volume.index, hourly_volume.values, marker='s', label=name, alpha=0.7)
        
        ax.set_xlabel('Hour (UTC)')
        ax.set_ylabel('Average Volume')
        ax.set_title('Hourly Volume Patterns')
        ax.set_xticks(range(0, 24, 2))
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Plot 5: Volatility over time
        ax = axes[2, 0]
        for name, df in self.data.items():
            if 'day' in name and not df.empty and 'volatility' in df.columns:
                ax.plot(df['datetime'], df['volatility'], label=name, alpha=0.7)
        
        # Add recent tracking volatility
        ax.axhline(y=self.recent_tracking['volatility'], color='red', linestyle='--', 
                  label=f"Recent: {self.recent_tracking['volatility']:.2f}%", alpha=0.5)
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Volatility (%)')
        ax.set_title('Historical Volatility')
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Plot 6: Performance comparison
        ax = axes[2, 1]
        
        # Create comparison data
        comparison_data = {
            'Recent\n5h': self.recent_tracking['price_change_pct'],
            'Hist\nAvg 5h': 0,
            'Hist\n95th %': 0,
            'Hist\n5th %': 0
        }
        
        # Get historical 5h statistics
        for name, df in self.data.items():
            if 'hour' in name and not df.empty:
                rolling_5h = df['close'].pct_change(5) * 100
                comparison_data['Hist\nAvg 5h'] = rolling_5h.mean()
                comparison_data['Hist\n95th %'] = rolling_5h.quantile(0.95)
                comparison_data['Hist\n5th %'] = rolling_5h.quantile(0.05)
                break
        
        colors = ['red' if v < 0 else 'green' for v in comparison_data.values()]
        bars = ax.bar(comparison_data.keys(), comparison_data.values(), color=colors, alpha=0.7)
        
        ax.set_ylabel('Return (%)')
        ax.set_title('5-Hour Performance Comparison')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for bar, value in zip(bars, comparison_data.values()):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{value:.2f}%', ha='center', va='bottom' if height > 0 else 'top')
        
        plt.tight_layout()
        
        # Save plot
        output_file = Path('sol_historical_analysis.png')
        plt.savefig(output_file, dpi=100, bbox_inches='tight')
        print(f"\nPlots saved to: {output_file}")
        
        plt.show()
    
    def save_analysis_report(self):
        """Save analysis results to JSON"""
        output_file = Path(f"sol_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        # Prepare report
        report = {
            'analysis_date': datetime.now().isoformat(),
            'recent_tracking': self.recent_tracking,
            'analysis_results': self.analysis_results,
            'data_files_analyzed': {name: str(path) for name, path in self.data_files.items()},
            'data_date_ranges': {}
        }
        
        # Add date ranges
        for name, df in self.data.items():
            if df is not None and not df.empty:
                report['data_date_ranges'][name] = {
                    'start': df['datetime'].min().isoformat(),
                    'end': df['datetime'].max().isoformat(),
                    'records': len(df)
                }
        
        # Save to JSON
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\nAnalysis report saved to: {output_file}")
        
        return output_file
    
    def run_complete_analysis(self):
        """Run complete analysis pipeline"""
        print("\n" + "="*70)
        print("BINANCE HISTORICAL DATA ANALYSIS FOR SOL")
        print("="*70)
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load data
        self.load_data()
        
        if not self.data:
            print("\n No data loaded. Please check file paths.")
            return
        
        # Run analyses
        self.analyze_price_patterns()
        self.analyze_volume_patterns()
        self.analyze_momentum_cycles()
        self.analyze_optimal_trading_times()
        self.compare_with_recent_tracking()
        self.generate_trading_recommendations()
        
        # Generate visualizations
        try:
            self.visualize_analysis()
        except Exception as e:
            print(f"\nCould not generate plots: {e}")
        
        # Save report
        self.save_analysis_report()
        
        print("\n" + "="*70)
        print("ANALYSIS COMPLETE")
        print("="*70)
        
        return self.analysis_results

if __name__ == "__main__":
    # Run analysis
    analyzer = BinanceHistoricalAnalyzer()
    results = analyzer.run_complete_analysis()