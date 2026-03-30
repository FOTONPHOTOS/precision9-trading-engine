import json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MarketDataAnalyzer:
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
        
        return pd.DataFrame(records)
    
    def analyze_tp_sl_behavior(self, entry_price, sl_price, tp_price, direction='LONG'):
        """Analyze how price behavior changes as it approaches TP/SL levels"""
        df = self.convert_to_dataframe()
        df['distance_to_sl'] = abs(df['current_price'] - sl_price) if 'current_price' in df.columns else np.nan
        df['distance_to_tp'] = abs(df['current_price'] - tp_price) if 'current_price' in df.columns else np.nan
        df['distance_to_entry'] = abs(df['current_price'] - entry_price) if 'current_price' in df.columns else np.nan
        
        # Determine if we're closer to TP than to SL
        df['closer_to_tp_than_sl'] = df['distance_to_tp'] < df['distance_to_sl'] if 'distance_to_tp' in df.columns and 'distance_to_sl' in df.columns else False
        
        # Identify when we're near TP (within 10% of total move)
        total_move = abs(tp_price - entry_price)
        df['near_tp'] = (df['distance_to_tp'] / total_move) <= 0.1 if 'distance_to_tp' in df.columns and total_move > 0 else False
        df['near_sl'] = (df['distance_to_sl'] / total_move) <= 0.1 if 'distance_to_sl' in df.columns and total_move > 0 else False
        
        # Calculate momentum metrics
        if 'current_price' in df.columns:
            df['price_velocity'] = df['current_price'].diff() / (df['timestamp'].diff() if 'timestamp' in df.columns else 0.1)
            df['price_acceleration'] = df['price_velocity'].diff()
        
        # Analyze order flow metrics when near targets
        near_tp_analysis = df[df['near_tp']].describe()
        near_sl_analysis = df[df['near_sl']].describe()
        
        print("=== Analysis When Near Take Profit ===")
        print(near_tp_analysis[['current_price', 'spread_pct', 'bid_ask_ratio', 'buy_sell_ratio', 'price_velocity', 'trade_imbalance']])
        
        print("\n=== Analysis When Near Stop Loss ===")
        print(near_sl_analysis[['current_price', 'spread_pct', 'bid_ask_ratio', 'buy_sell_ratio', 'price_velocity', 'trade_imbalance']])
        
        return df, near_tp_analysis, near_sl_analysis
    
    def find_fakeout_patterns(self):
        """Identify patterns where price approaches TP but reverses"""
        df = self.convert_to_dataframe()
        
        # Look for periods where price was near TP but then moved in the opposite direction
        # This is complex without knowing actual entry/exit parameters, so we'll identify price reversals
        if 'current_price' in df.columns:
            df['price_change'] = df['current_price'].pct_change()
            df['high_price_change'] = df['kline_high'].pct_change() if 'kline_high' in df.columns else 0
            df['low_price_change'] = df['kline_low'].pct_change() if 'kline_low' in df.columns else 0
            
            # Identify rapid reversals (where price moves in one direction then quickly in the other)
            df['rapid_reversal'] = (
                (abs(df['price_change'].shift(1)) > 0.0005) &  # Previous movement significant
                (df['price_change'].shift(1) * df['price_change'] < 0) &  # Opposite direction
                (abs(df['price_change']) > 0.0005)  # Current movement significant
            )
            
            fakeout_events = df[df['rapid_reversal']]
            print(f"Found {len(fakeout_events)} potential fakeout events")
            
            if len(fakeout_events) > 0:
                print("Fakeout event details:")
                print(fakeout_events[['utc_time', 'current_price', 'price_change', 'spread_pct', 'buy_sell_ratio', 'trade_imbalance']])
        
        return df

def main():
    # Load the captured market data file
    data_files = list(Path('.').glob('market_data_capture_*.json'))
    if not data_files:
        print("No captured data files found!")
        return
    
    latest_file = sorted(data_files, key=lambda x: x.name)[-1]
    print(f"Analyzing data from: {latest_file}")
    
    analyzer = MarketDataAnalyzer(latest_file)
    
    # Example analysis - you would need to know your typical entry/exit parameters
    # For demonstration, let's use approximate values from the captured data
    df = analyzer.convert_to_dataframe()
    if 'current_price' in df.columns:
        # Use a sample entry scenario based on recent market conditions
        sample_entry_price = df['current_price'].iloc[0]
        sample_tp_price = sample_entry_price * 1.005  # 0.5% target
        sample_sl_price = sample_entry_price * 0.999  # 0.1% stop loss
        
        print(f"Sample analysis for entry: {sample_entry_price}, TP: {sample_tp_price}, SL: {sample_sl_price}")
        df_analysis, near_tp, near_sl = analyzer.analyze_tp_sl_behavior(
            sample_entry_price, sample_sl_price, sample_tp_price
        )
    
    # Find potential fakeout patterns
    analyzer.find_fakeout_patterns()

if __name__ == "__main__":
    main()