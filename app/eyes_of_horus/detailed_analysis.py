import json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DetailedMarketAnalyzer:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = self.load_data()
        
    def load_data(self):
        """Load the captured market data"""
        with open(self.data_file, 'r') as f:
            return json.load(f)
    
    def convert_to_dataframe(self):
        """Convert raw captured data to a structured DataFrame"""
        records = []
        
        for snapshot in self.data:
            record = {
                'timestamp': snapshot['timestamp'],
                'utc_time': snapshot['utc_time'],
                'symbol': snapshot['symbol'],
            }
            
            # Extract kline data
            kline_data = snapshot['data']['klines_1m'][0] if snapshot['data']['klines_1m'] else [None]*7
            if kline_data:
                record.update({
                    'kline_time': kline_data[0],
                    'kline_open': float(kline_data[1]),
                    'kline_high': float(kline_data[2]),
                    'kline_low': float(kline_data[3]),
                    'kline_close': float(kline_data[4]),
                    'kline_volume': float(kline_data[5])
                })
            
            # Extract orderbook data
            orderbook = snapshot['data']['orderbook']
            if orderbook:
                if 'b' in orderbook:  # New format
                    bids = orderbook['b']
                    asks = orderbook['a']
                else:  # Old format
                    bids = orderbook.get('bids', [])
                    asks = orderbook.get('asks', [])
                
                if bids:
                    record['best_bid'] = float(bids[0][0])
                    record['best_bid_size'] = float(bids[0][1])
                    # Calculate bid-ask spread
                    if asks and len(asks) > 0:
                        record['best_ask'] = float(asks[0][0])
                        record['best_ask_size'] = float(asks[0][1])
                        record['spread'] = record['best_ask'] - record['best_bid']
                        record['spread_pct'] = (record['spread'] / record['best_bid']) * 10000  # in basis points
                    else:
                        record['best_ask'] = None
                        record['best_ask_size'] = None
                        record['spread'] = None
                        record['spread_pct'] = None
                
                # Calculate bid-ask imbalance (top 5 levels)
                top_5_bid_size = sum(float(bid[1]) for bid in bids[:5]) if bids else 0
                top_5_ask_size = sum(float(ask[1]) for ask in asks[:5]) if asks else 0
                record['bid_ask_imbalance'] = top_5_bid_size - top_5_ask_size
                record['bid_ask_ratio'] = top_5_bid_size / top_5_ask_size if top_5_ask_size > 0 else float('inf')
            
            # Extract recent trades data
            recent_trades = snapshot['data']['recent_trades']
            if recent_trades:
                # Calculate recent trade metrics
                recent_buys = [t for t in recent_trades if t['side'] == 'Buy']
                recent_sells = [t for t in recent_trades if t['side'] == 'Sell']
                
                total_buy_volume = sum(float(t['size']) for t in recent_buys)
                total_sell_volume = sum(float(t['size']) for t in recent_sells)
                
                record.update({
                    'total_recent_volume': total_buy_volume + total_sell_volume,
                    'recent_buy_volume': total_buy_volume,
                    'recent_sell_volume': total_sell_volume,
                    'buy_sell_ratio': total_buy_volume / total_sell_volume if total_sell_volume > 0 else float('inf'),
                    'trade_imbalance': total_buy_volume - total_sell_volume,
                    'num_recent_trades': len(recent_trades)
                })
            
            # Extract current price
            if snapshot['data']['current_price']:
                record['current_price'] = snapshot['data']['current_price']
            
            records.append(record)
        
        df = pd.DataFrame(records)
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Calculate derived metrics
        if 'current_price' in df.columns:
            df['price_velocity'] = df['current_price'].diff() / df['timestamp'].diff()
            df['price_acceleration'] = df['price_velocity'].diff()
            df['price_momentum'] = df['current_price'].diff(2)  # 2-period momentum
            df['volatility'] = df['current_price'].rolling(window=10).std()
        
        return df
    
    def analyze_microstructural_patterns(self):
        """Analyze patterns that are relevant for microstructural scalping"""
        df = self.convert_to_dataframe()
        
        print("=== Basic Market Statistics ===")
        if 'current_price' in df.columns:
            print(f"Price range: {df['current_price'].min():.2f} - {df['current_price'].max():.2f}")
            print(f"Average price: {df['current_price'].mean():.2f}")
            print(f"Price volatility (std): {df['current_price'].std():.2f}")
        
        print(f"\nTotal snapshots: {len(df)}")
        print(f"Time range: {df['utc_time'].iloc[0]} to {df['utc_time'].iloc[-1]}")
        
        print("\n=== Spread Analysis ===")
        if 'spread_pct' in df.columns:
            print(f"Average spread: {df['spread_pct'].mean():.4f} bps")
            print(f"Spread std: {df['spread_pct'].std():.4f}")
            print(f"Max spread: {df['spread_pct'].max():.4f} bps")
        
        print("\n=== Volume Analysis ===")
        if 'total_recent_volume' in df.columns:
            print(f"Average volume per snapshot: {df['total_recent_volume'].mean():.6f}")
            print(f"Volume std: {df['total_recent_volume'].std():.6f}")
            print(f"Max volume: {df['total_recent_volume'].max():.6f}")
        
        print("\n=== Order Flow Analysis ===")
        if 'buy_sell_ratio' in df.columns:
            print(f"Average buy/sell ratio: {df['buy_sell_ratio'].mean():.4f}")
            print(f"Ratio std: {df['buy_sell_ratio'].std():.4f}")
        
        if 'trade_imbalance' in df.columns:
            print(f"Average trade imbalance: {df['trade_imbalance'].mean():.6f}")
            print(f"Imbalance std: {df['trade_imbalance'].std():.6f}")
        
        # Find periods of high volatility - these might correlate with fakeouts
        if 'volatility' in df.columns:
            high_volatility_threshold = df['volatility'].quantile(0.8)  # Top 20% volatility
            high_vol_periods = df[df['volatility'] > high_volatility_threshold]
            
            print(f"\n=== High Volatility Periods ===")
            print(f"Number of high vol periods: {len(high_vol_periods)}")
            if not high_vol_periods.empty:
                print(f"Average spread during high volatility: {high_vol_periods['spread_pct'].mean() if 'spread_pct' in high_vol_periods.columns else 'N/A':.4f}")
                print(f"Average buy/sell ratio during high volatility: {high_vol_periods['buy_sell_ratio'].mean() if 'buy_sell_ratio' in high_vol_periods.columns else 'N/A':.4f}")
        
        return df
    
    def identify_tp_sl_zones_for_microscalping(self):
        """Identify potential zones for micro-scalping based on the captured data"""
        df = self.convert_to_dataframe()
        
        if 'current_price' not in df.columns:
            print("No price data available for analysis")
            return
        
        print("=== Micro-scalping Opportunity Analysis ===")
        
        # Find periods where price moved significantly (0.1%+ which would be a potential scalp target)
        price_changes = df['current_price'].pct_change()
        
        # Identify significant moves in the data
        significant_moves = price_changes[abs(price_changes) > 0.001]  # More than 0.1%
        
        if len(significant_moves) > 0:
            print(f"Found {len(significant_moves)} periods with moves > 0.1%:")
            
            for idx in significant_moves.index[:10]:  # Show first 10 significant moves
                current_time = df.loc[idx, 'utc_time']
                current_price = df.loc[idx, 'current_price']
                if idx > 0:
                    prev_price = df.loc[idx-1, 'current_price']
                    move_pct = (current_price - prev_price) / prev_price * 100
                    print(f"  {current_time}: Price moved {move_pct:.3f}% from {prev_price:.2f} to {current_price:.2f}")
        
        # Look for momentum changes that might indicate fakeouts
        if 'price_velocity' in df.columns and 'price_acceleration' in df.columns:
            # Find points where velocity changes significantly (potential reversal points)
            velocity_changes = abs(df['price_acceleration'])
            high_change_threshold = velocity_changes.quantile(0.8)
            high_change_points = df[velocity_changes > high_change_threshold]
            
            print(f"\nFound {len(high_change_points)} high velocity change points (potential reversal/fakeout points)")
        
        # Analyze spread behavior during significant moves
        if 'spread_pct' in df.columns:
            # Look for spread widening during moves
            large_moves = df[abs(price_changes) > 0.001] if len(price_changes) > 0 else pd.DataFrame()
            if not large_moves.empty:
                avg_spread_during_moves = large_moves['spread_pct'].mean()
                overall_avg_spread = df['spread_pct'].mean()
                
                print(f"\nSpread behavior during >0.1% moves: {avg_spread_during_moves:.4f} bps (vs overall: {overall_avg_spread:.4f} bps)")
        
        return df

def main():
    # Load the captured market data file
    data_files = list(Path('.').glob('market_data_capture_*.json'))
    if not data_files:
        print("No captured data files found!")
        return
    
    latest_file = sorted(data_files, key=lambda x: x.name)[-1]
    print(f"Analyzing detailed data from: {latest_file}")
    
    analyzer = DetailedMarketAnalyzer(latest_file)
    
    # Perform detailed analysis
    df = analyzer.analyze_microstructural_patterns()
    
    # Identify micro-scalping zones
    analyzer.identify_tp_sl_zones_for_microscalping()

if __name__ == "__main__":
    main()