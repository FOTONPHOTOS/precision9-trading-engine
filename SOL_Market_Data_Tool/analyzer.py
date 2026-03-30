#!/usr/bin/env python3
"""
SOL Market Data Analyzer for Bot Calibration
============================================
Analyzes collected market data to identify patterns, correlations,
and optimal trading conditions for bot calibration.

Features:
- CVD vs Price correlation analysis
- Momentum pattern identification
- Optimal entry/exit conditions
- Risk/reward analysis
- Market regime classification
- Statistical analysis and visualization
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class SOLMarketDataAnalyzer:
    """Analyzes collected SOL market data for bot calibration"""
    
    def __init__(self, csv_files: list = None, data_dir: str = "sol_training_data"):
        """
        Initialize analyzer
        
        Args:
            csv_files: List of CSV files to analyze
            data_dir: Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        self.csv_files = csv_files or list(self.data_dir.glob("sol_market_data_*.csv"))
        self.df = None
        self.analysis_results = {}
        
    def load_data(self):
        """Load and combine all CSV files"""
        print(f"Loading {len(self.csv_files)} CSV files...")
        
        dfs = []
        for csv_file in self.csv_files:
            try:
                df = pd.read_csv(csv_file)
                dfs.append(df)
                print(f"  Loaded {len(df)} rows from {csv_file.name}")
            except Exception as e:
                print(f"  Error loading {csv_file}: {e}")
        
        if dfs:
            self.df = pd.concat(dfs, ignore_index=True)
            self.df['datetime'] = pd.to_datetime(self.df['datetime_utc'])
            self.df.set_index('datetime', inplace=True)
            print(f"\nTotal data points loaded: {len(self.df):,}")
            print(f"Date range: {self.df.index.min()} to {self.df.index.max()}")
        else:
            raise ValueError("No data loaded")
    
    def analyze_cvd_price_correlation(self):
        """Analyze correlation between CVD and price movements"""
        print("\n" + "="*60)
        print("CVD-PRICE CORRELATION ANALYSIS")
        print("="*60)
        
        results = {}
        
        # Overall correlation
        corr = self.df['cvd'].corr(self.df['price'])
        results['overall_correlation'] = corr
        print(f"Overall CVD-Price Correlation: {corr:.4f}")
        
        # Correlation by timeframe
        timeframes = {
            '1m': 'price_change_1m',
            '5m': 'price_change_5m'
        }
        
        for tf_name, tf_col in timeframes.items():
            corr_cvd_change = self.df[f'cvd_change_{tf_name}'].corr(self.df[tf_col])
            results[f'cvd_change_{tf_name}_correlation'] = corr_cvd_change
            print(f"CVD Change vs Price Change ({tf_name}): {corr_cvd_change:.4f}")
        
        # CVD velocity correlation
        cvd_vel_corr = self.df['cvd_velocity'].corr(self.df['momentum_1m'])
        results['cvd_velocity_momentum_correlation'] = cvd_vel_corr
        print(f"CVD Velocity vs Momentum: {cvd_vel_corr:.4f}")
        
        # Analyze CVD divergence
        print("\nCVD DIVERGENCE ANALYSIS:")
        
        # Bullish divergence: Price down, CVD up
        bullish_div = self.df[(self.df['price_change_1m'] < -0.1) & (self.df['cvd_change_1m'] > 0)]
        results['bullish_divergence_count'] = len(bullish_div)
        results['bullish_divergence_success_rate'] = len(bullish_div[bullish_div['price_change_5m'] > 0]) / max(len(bullish_div), 1)
        
        # Bearish divergence: Price up, CVD down
        bearish_div = self.df[(self.df['price_change_1m'] > 0.1) & (self.df['cvd_change_1m'] < 0)]
        results['bearish_divergence_count'] = len(bearish_div)
        results['bearish_divergence_success_rate'] = len(bearish_div[bearish_div['price_change_5m'] < 0]) / max(len(bearish_div), 1)
        
        print(f"  Bullish Divergences: {results['bullish_divergence_count']} (Success: {results['bullish_divergence_success_rate']*100:.1f}%)")
        print(f"  Bearish Divergences: {results['bearish_divergence_count']} (Success: {results['bearish_divergence_success_rate']*100:.1f}%)")
        
        self.analysis_results['cvd_correlation'] = results
        return results
    
    def analyze_optimal_entry_conditions(self):
        """Identify optimal entry conditions based on historical data"""
        print("\n" + "="*60)
        print("OPTIMAL ENTRY CONDITIONS ANALYSIS")
        print("="*60)
        
        results = {}
        
        # Define successful trades (price moved favorably by 0.5% within 5 minutes)
        self.df['successful_long'] = self.df['price_change_5m'] > 0.5
        self.df['successful_short'] = self.df['price_change_5m'] < -0.5
        
        # Analyze conditions for successful longs
        print("\nSUCCESSFUL LONG CONDITIONS:")
        long_conditions = {}
        
        successful_longs = self.df[self.df['successful_long']]
        
        # Average conditions
        long_conditions['avg_cvd_change_1m'] = successful_longs['cvd_change_1m'].mean()
        long_conditions['avg_momentum_1m'] = successful_longs['momentum_1m'].mean()
        long_conditions['avg_rsi'] = successful_longs['rsi_14'].mean()
        long_conditions['avg_volume_ratio'] = successful_longs['buy_sell_ratio'].mean()
        long_conditions['avg_book_imbalance'] = successful_longs['book_imbalance'].mean()
        
        print(f"  Avg CVD Change (1m): {long_conditions['avg_cvd_change_1m']:.2f}")
        print(f"  Avg Momentum (1m): {long_conditions['avg_momentum_1m']:.4f}")
        print(f"  Avg RSI: {long_conditions['avg_rsi']:.1f}")
        print(f"  Avg Buy/Sell Ratio: {long_conditions['avg_volume_ratio']:.2f}")
        print(f"  Avg Book Imbalance: {long_conditions['avg_book_imbalance']:.3f}")
        
        # Analyze conditions for successful shorts
        print("\nSUCCESSFUL SHORT CONDITIONS:")
        short_conditions = {}
        
        successful_shorts = self.df[self.df['successful_short']]
        
        short_conditions['avg_cvd_change_1m'] = successful_shorts['cvd_change_1m'].mean()
        short_conditions['avg_momentum_1m'] = successful_shorts['momentum_1m'].mean()
        short_conditions['avg_rsi'] = successful_shorts['rsi_14'].mean()
        short_conditions['avg_volume_ratio'] = successful_shorts['buy_sell_ratio'].mean()
        short_conditions['avg_book_imbalance'] = successful_shorts['book_imbalance'].mean()
        
        print(f"  Avg CVD Change (1m): {short_conditions['avg_cvd_change_1m']:.2f}")
        print(f"  Avg Momentum (1m): {short_conditions['avg_momentum_1m']:.4f}")
        print(f"  Avg RSI: {short_conditions['avg_rsi']:.1f}")
        print(f"  Avg Buy/Sell Ratio: {short_conditions['avg_volume_ratio']:.2f}")
        print(f"  Avg Book Imbalance: {short_conditions['avg_book_imbalance']:.3f}")
        
        results['long_conditions'] = long_conditions
        results['short_conditions'] = short_conditions
        
        # Find best combination of indicators
        print("\nBEST INDICATOR COMBINATIONS:")
        
        # Test various threshold combinations
        best_long_combo = self._find_best_indicator_combo('long')
        best_short_combo = self._find_best_indicator_combo('short')
        
        results['best_long_combo'] = best_long_combo
        results['best_short_combo'] = best_short_combo
        
        print(f"\nBest Long Combo: {best_long_combo['description']}")
        print(f"  Success Rate: {best_long_combo['success_rate']*100:.1f}%")
        print(f"  Signal Count: {best_long_combo['signal_count']}")
        
        print(f"\nBest Short Combo: {best_short_combo['description']}")
        print(f"  Success Rate: {best_short_combo['success_rate']*100:.1f}%")
        print(f"  Signal Count: {best_short_combo['signal_count']}")
        
        self.analysis_results['entry_conditions'] = results
        return results
    
    def _find_best_indicator_combo(self, direction='long'):
        """Find best combination of indicators for entry"""
        best_combo = {'success_rate': 0, 'signal_count': 0, 'description': ''}
        
        if direction == 'long':
            target = 'successful_long'
            cvd_threshold = 10
            momentum_threshold = 0.1
            rsi_low = 30
            rsi_high = 70
        else:
            target = 'successful_short'
            cvd_threshold = -10
            momentum_threshold = -0.1
            rsi_low = 30
            rsi_high = 70
        
        # Test different combinations
        combos = [
            {
                'name': 'CVD + Momentum',
                'condition': (self.df['cvd_change_1m'] > cvd_threshold if direction == 'long' else self.df['cvd_change_1m'] < cvd_threshold) & 
                            (self.df['momentum_1m'] > momentum_threshold if direction == 'long' else self.df['momentum_1m'] < momentum_threshold)
            },
            {
                'name': 'CVD + RSI',
                'condition': (self.df['cvd_change_1m'] > cvd_threshold if direction == 'long' else self.df['cvd_change_1m'] < cvd_threshold) & 
                            (self.df['rsi_14'] < rsi_low if direction == 'long' else self.df['rsi_14'] > rsi_high)
            },
            {
                'name': 'CVD + Volume + Book',
                'condition': (self.df['cvd_change_1m'] > cvd_threshold if direction == 'long' else self.df['cvd_change_1m'] < cvd_threshold) & 
                            (self.df['buy_sell_ratio'] > 1.2 if direction == 'long' else self.df['buy_sell_ratio'] < 0.8) &
                            (self.df['book_imbalance'] > 0.1 if direction == 'long' else self.df['book_imbalance'] < -0.1)
            },
            {
                'name': 'Full Combo',
                'condition': (self.df['cvd_change_1m'] > cvd_threshold if direction == 'long' else self.df['cvd_change_1m'] < cvd_threshold) & 
                            (self.df['momentum_1m'] > momentum_threshold if direction == 'long' else self.df['momentum_1m'] < momentum_threshold) &
                            (self.df['rsi_14'] < 60 if direction == 'long' else self.df['rsi_14'] > 40) &
                            (self.df['unusual_volume'] == True)
            }
        ]
        
        for combo in combos:
            signals = self.df[combo['condition']]
            if len(signals) > 0:
                success_rate = len(signals[signals[target]]) / len(signals)
                if success_rate > best_combo['success_rate'] and len(signals) > 10:
                    best_combo = {
                        'success_rate': success_rate,
                        'signal_count': len(signals),
                        'description': combo['name'],
                        'successful_trades': len(signals[signals[target]])
                    }
        
        return best_combo
    
    def analyze_market_regimes(self):
        """Analyze performance across different market regimes"""
        print("\n" + "="*60)
        print("MARKET REGIME ANALYSIS")
        print("="*60)
        
        results = {}
        
        # Group by regime
        regime_groups = self.df.groupby('regime')
        
        print("\nREGIME DISTRIBUTION:")
        for regime, group in regime_groups:
            pct = len(group) / len(self.df) * 100
            avg_return = group['price_change_5m'].mean()
            volatility = group['volatility_1m'].mean()
            
            results[regime] = {
                'percentage': pct,
                'avg_return_5m': avg_return,
                'avg_volatility': volatility,
                'count': len(group)
            }
            
            print(f"  {regime}: {pct:.1f}% | Avg Return: {avg_return:.3f}% | Volatility: {volatility:.4f}")
        
        # Best regime for trading
        print("\nBEST TRADING CONDITIONS BY REGIME:")
        
        for regime, group in regime_groups:
            # Success rate for longs and shorts
            long_success = len(group[group['price_change_5m'] > 0.5]) / max(len(group), 1)
            short_success = len(group[group['price_change_5m'] < -0.5]) / max(len(group), 1)
            
            print(f"  {regime}:")
            print(f"    Long Success Rate: {long_success*100:.1f}%")
            print(f"    Short Success Rate: {short_success*100:.1f}%")
            
            results[regime]['long_success'] = long_success
            results[regime]['short_success'] = short_success
        
        self.analysis_results['market_regimes'] = results
        return results
    
    def analyze_risk_metrics(self):
        """Analyze risk metrics for position sizing and stop losses"""
        print("\n" + "="*60)
        print("RISK METRICS ANALYSIS")
        print("="*60)
        
        results = {}
        
        # Calculate maximum adverse excursion (MAE)
        print("\nMAXIMUM ADVERSE EXCURSION (MAE):")
        
        # For successful longs, what was the max drawdown before profit?
        successful_longs = self.df[self.df['successful_long']]
        mae_long = successful_longs['low_1m'] - successful_longs['price']
        results['mae_long_mean'] = mae_long.mean()
        results['mae_long_95pct'] = mae_long.quantile(0.05)  # 95% of trades have MAE better than this
        
        print(f"  Long MAE Mean: {results['mae_long_mean']:.4f}")
        print(f"  Long MAE 95%: {results['mae_long_95pct']:.4f}")
        
        # For successful shorts
        successful_shorts = self.df[self.df['successful_short']]
        mae_short = successful_shorts['price'] - successful_shorts['high_1m']
        results['mae_short_mean'] = mae_short.mean()
        results['mae_short_95pct'] = mae_short.quantile(0.95)
        
        print(f"  Short MAE Mean: {results['mae_short_mean']:.4f}")
        print(f"  Short MAE 95%: {results['mae_short_95pct']:.4f}")
        
        # Optimal stop loss analysis
        print("\nOPTIMAL STOP LOSS ANALYSIS:")
        
        stop_losses = [0.1, 0.2, 0.3, 0.4, 0.5]  # Percentage stop losses
        
        for sl in stop_losses:
            # Calculate win rate with this stop loss
            long_stopped = (self.df['low_1m'] < self.df['price'] * (1 - sl/100)).sum()
            short_stopped = (self.df['high_1m'] > self.df['price'] * (1 + sl/100)).sum()
            
            total_trades = len(self.df)
            stop_rate = (long_stopped + short_stopped) / (2 * total_trades)
            
            print(f"  {sl}% Stop Loss - Stop Rate: {stop_rate*100:.1f}%")
            
            results[f'stop_loss_{sl}pct'] = stop_rate
        
        # Volatility-based position sizing
        print("\nVOLATILITY-BASED POSITION SIZING:")
        
        volatility_percentiles = [25, 50, 75, 90]
        for pct in volatility_percentiles:
            vol_threshold = self.df['volatility_1m'].quantile(pct/100)
            print(f"  {pct}th percentile volatility: {vol_threshold:.6f}")
            results[f'volatility_p{pct}'] = vol_threshold
        
        # Suggested position sizing based on volatility
        avg_volatility = self.df['volatility_1m'].mean()
        results['avg_volatility'] = avg_volatility
        results['suggested_base_position_size'] = 1.0 / (avg_volatility * 100)  # Inverse volatility sizing
        
        print(f"\nSuggested base position size: {results['suggested_base_position_size']:.2f}x")
        
        self.analysis_results['risk_metrics'] = results
        return results
    
    def analyze_timing_patterns(self):
        """Analyze timing patterns for optimal trading hours"""
        print("\n" + "="*60)
        print("TIMING PATTERNS ANALYSIS")
        print("="*60)
        
        results = {}
        
        # Add hour column
        self.df['hour'] = self.df.index.hour
        
        # Analyze by hour
        hourly_stats = self.df.groupby('hour').agg({
            'volatility_1m': 'mean',
            'volume_1m': 'mean',
            'successful_long': 'mean',
            'successful_short': 'mean',
            'unusual_volume': 'sum'
        })
        
        print("\nHOURLY PATTERNS (UTC):")
        print("Hour | Volatility | Volume   | Long% | Short% | Unusual")
        print("-" * 60)
        
        for hour in range(24):
            if hour in hourly_stats.index:
                row = hourly_stats.loc[hour]
                print(f" {hour:02d}  | {row['volatility_1m']:.6f} | {row['volume_1m']:8.2f} | {row['successful_long']*100:5.1f} | {row['successful_short']*100:6.1f} | {row['unusual_volume']:7.0f}")
        
        # Find best trading hours
        best_hours_long = hourly_stats.nlargest(3, 'successful_long').index.tolist()
        best_hours_short = hourly_stats.nlargest(3, 'successful_short').index.tolist()
        most_volatile_hours = hourly_stats.nlargest(3, 'volatility_1m').index.tolist()
        
        results['best_hours_long'] = best_hours_long
        results['best_hours_short'] = best_hours_short
        results['most_volatile_hours'] = most_volatile_hours
        
        print(f"\nBest hours for longs: {best_hours_long}")
        print(f"Best hours for shorts: {best_hours_short}")
        print(f"Most volatile hours: {most_volatile_hours}")
        
        self.analysis_results['timing_patterns'] = results
        return results
    
    def generate_calibration_report(self):
        """Generate comprehensive calibration report for bot tuning"""
        print("\n" + "="*60)
        print("BOT CALIBRATION RECOMMENDATIONS")
        print("="*60)
        
        recommendations = {}
        
        # CVD thresholds
        cvd_long_threshold = self.df[self.df['successful_long']]['cvd_change_1m'].quantile(0.3)
        cvd_short_threshold = self.df[self.df['successful_short']]['cvd_change_1m'].quantile(0.7)
        
        recommendations['cvd_thresholds'] = {
            'long_entry': cvd_long_threshold,
            'short_entry': cvd_short_threshold
        }
        
        print(f"\nCVD THRESHOLDS:")
        print(f"  Long Entry: CVD Change > {cvd_long_threshold:.2f}")
        print(f"  Short Entry: CVD Change < {cvd_short_threshold:.2f}")
        
        # Momentum thresholds
        momentum_long = self.df[self.df['successful_long']]['momentum_1m'].quantile(0.3)
        momentum_short = self.df[self.df['successful_short']]['momentum_1m'].quantile(0.7)
        
        recommendations['momentum_thresholds'] = {
            'long_entry': momentum_long,
            'short_entry': momentum_short
        }
        
        print(f"\nMOMENTUM THRESHOLDS:")
        print(f"  Long Entry: Momentum > {momentum_long:.4f}")
        print(f"  Short Entry: Momentum < {momentum_short:.4f}")
        
        # RSI levels
        rsi_oversold = self.df[self.df['successful_long']]['rsi_14'].quantile(0.7)
        rsi_overbought = self.df[self.df['successful_short']]['rsi_14'].quantile(0.3)
        
        recommendations['rsi_levels'] = {
            'oversold': rsi_oversold,
            'overbought': rsi_overbought
        }
        
        print(f"\nRSI LEVELS:")
        print(f"  Oversold (Long): RSI < {rsi_oversold:.1f}")
        print(f"  Overbought (Short): RSI > {rsi_overbought:.1f}")
        
        # Volume filters
        volume_threshold = self.df['volume_1m'].quantile(0.7)
        unusual_volume_multiplier = self.df[self.df['unusual_volume']]['volume_1m'].mean() / self.df['volume_1m'].mean()
        
        recommendations['volume_filters'] = {
            'min_volume': volume_threshold,
            'unusual_multiplier': unusual_volume_multiplier
        }
        
        print(f"\nVOLUME FILTERS:")
        print(f"  Minimum Volume: {volume_threshold:.2f}")
        print(f"  Unusual Volume Multiplier: {unusual_volume_multiplier:.2f}x")
        
        # Risk parameters
        recommendations['risk_parameters'] = {
            'stop_loss_pct': 0.3,  # Based on MAE analysis
            'take_profit_pct': 0.5,  # Based on successful trade threshold
            'max_position_volatility_multiplier': 2.0,
            'base_position_size': self.analysis_results.get('risk_metrics', {}).get('suggested_base_position_size', 1.0)
        }
        
        print(f"\nRISK PARAMETERS:")
        print(f"  Stop Loss: 0.3%")
        print(f"  Take Profit: 0.5%")
        print(f"  Position Size: {recommendations['risk_parameters']['base_position_size']:.2f}x base")
        
        # Market regime filters
        best_regimes_long = []
        best_regimes_short = []
        
        if 'market_regimes' in self.analysis_results:
            for regime, stats in self.analysis_results['market_regimes'].items():
                if stats.get('long_success', 0) > 0.05:
                    best_regimes_long.append(regime)
                if stats.get('short_success', 0) > 0.05:
                    best_regimes_short.append(regime)
        
        recommendations['regime_filters'] = {
            'allowed_long_regimes': best_regimes_long,
            'allowed_short_regimes': best_regimes_short
        }
        
        print(f"\nREGIME FILTERS:")
        print(f"  Long in: {', '.join(best_regimes_long)}")
        print(f"  Short in: {', '.join(best_regimes_short)}")
        
        # Trading hours
        if 'timing_patterns' in self.analysis_results:
            recommendations['trading_hours'] = {
                'best_long_hours_utc': self.analysis_results['timing_patterns'].get('best_hours_long', []),
                'best_short_hours_utc': self.analysis_results['timing_patterns'].get('best_hours_short', []),
                'avoid_hours_utc': self.analysis_results['timing_patterns'].get('most_volatile_hours', [])
            }
            
            print(f"\nTRADING HOURS (UTC):")
            print(f"  Best Long Hours: {recommendations['trading_hours']['best_long_hours_utc']}")
            print(f"  Best Short Hours: {recommendations['trading_hours']['best_short_hours_utc']}")
        
        self.analysis_results['calibration'] = recommendations
        
        # Save to JSON
        output_file = self.data_dir / f"calibration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
        
        print(f"\nCalibration report saved to: {output_file}")
        
        return recommendations
    
    def plot_analysis(self):
        """Generate visualization plots"""
        print("\n" + "="*60)
        print("GENERATING VISUALIZATIONS")
        print("="*60)
        
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        
        # CVD vs Price scatter
        ax = axes[0, 0]
        sample = self.df.sample(min(10000, len(self.df)))
        ax.scatter(sample['cvd_change_1m'], sample['price_change_1m'], alpha=0.3, s=1)
        ax.set_xlabel('CVD Change (1m)')
        ax.set_ylabel('Price Change (1m) %')
        ax.set_title('CVD vs Price Movement')
        ax.grid(True, alpha=0.3)
        
        # Success rate by CVD bins
        ax = axes[0, 1]
        cvd_bins = pd.qcut(self.df['cvd_change_1m'], q=10)
        success_by_cvd = self.df.groupby(cvd_bins)['successful_long'].mean()
        success_by_cvd.plot(kind='bar', ax=ax)
        ax.set_xlabel('CVD Change Bins')
        ax.set_ylabel('Long Success Rate')
        ax.set_title('Success Rate by CVD Level')
        ax.tick_params(axis='x', rotation=45)
        
        # Hourly patterns
        ax = axes[1, 0]
        hourly_volatility = self.df.groupby('hour')['volatility_1m'].mean()
        hourly_volatility.plot(kind='line', ax=ax, marker='o')
        ax.set_xlabel('Hour (UTC)')
        ax.set_ylabel('Average Volatility')
        ax.set_title('Volatility by Hour')
        ax.grid(True, alpha=0.3)
        
        # Regime distribution
        ax = axes[1, 1]
        regime_counts = self.df['regime'].value_counts()
        regime_counts.plot(kind='pie', ax=ax, autopct='%1.1f%%')
        ax.set_title('Market Regime Distribution')
        
        # Risk-Reward scatter
        ax = axes[2, 0]
        ax.scatter(self.df['volatility_1m'], self.df['price_change_5m'].abs(), alpha=0.3, s=1)
        ax.set_xlabel('Volatility (1m)')
        ax.set_ylabel('Absolute Price Change (5m) %')
        ax.set_title('Risk vs Reward')
        ax.grid(True, alpha=0.3)
        
        # CVD acceleration distribution
        ax = axes[2, 1]
        self.df['cvd_acceleration'].hist(bins=50, ax=ax, alpha=0.7)
        ax.set_xlabel('CVD Acceleration')
        ax.set_ylabel('Frequency')
        ax.set_title('CVD Acceleration Distribution')
        ax.axvline(0, color='red', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        # Save plot
        plot_file = self.data_dir / f"analysis_plots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(plot_file, dpi=100)
        print(f"Plots saved to: {plot_file}")
        
        plt.show()
    
    def run_complete_analysis(self):
        """Run complete analysis pipeline"""
        print("\n" + "="*60)
        print("RUNNING COMPLETE SOL MARKET ANALYSIS")
        print("="*60)
        
        # Load data
        self.load_data()
        
        # Run all analyses
        self.analyze_cvd_price_correlation()
        self.analyze_optimal_entry_conditions()
        self.analyze_market_regimes()
        self.analyze_risk_metrics()
        self.analyze_timing_patterns()
        
        # Generate calibration report
        self.generate_calibration_report()
        
        # Generate plots
        try:
            self.plot_analysis()
        except Exception as e:
            print(f"Could not generate plots: {e}")
        
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        
        return self.analysis_results

if __name__ == "__main__":
    # Example usage
    analyzer = SOLMarketDataAnalyzer(data_dir="sol_training_data")
    
    # Run complete analysis
    results = analyzer.run_complete_analysis()
    
    print("\nAnalysis complete! Check the output files in 'sol_training_data' directory.")