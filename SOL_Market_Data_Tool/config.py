"""
Configuration file for SOL Market Data Tool
Modify these settings as needed for your environment
"""

# Redis Configuration
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True,
    'encoding': 'utf-8',
    'max_connections': 10
}

# Data Collection Settings
COLLECTION_CONFIG = {
    'symbol': 'SOLUSDT',
    'data_dir': 'sol_training_data',
    'rotation_hours': 6,  # Rotate CSV files every 6 hours
    'collection_interval': 1,  # Collect data every 1 second
    'max_history_size': 10000,  # Maximum data points to keep in memory
}

# Redis Channel Subscriptions
REDIS_CHANNELS = [
    'trades:{symbol}',
    'analytics:trade:{symbol}',
    'orderbook:{symbol}',
    'analytics:{symbol}'
]

# Analysis Settings
ANALYSIS_CONFIG = {
    'min_data_points': 1000,  # Minimum data points needed for analysis
    'success_threshold_long': 0.5,  # 0.5% price increase for successful long
    'success_threshold_short': -0.5,  # 0.5% price decrease for successful short
    'max_sample_size': 10000,  # Maximum points to use for visualization
}

# Market Regime Thresholds
REGIME_THRESHOLDS = {
    'trending_threshold': 0.3,  # % price change to consider trending
    'high_volatility': 0.5,  # Volatility threshold for high volatility regime
    'unusual_volume_multiplier': 3.0,  # Multiplier for unusual volume detection
    'large_trade_multiplier': 10.0,  # Multiplier for large trade detection
}

# Risk Management Defaults
RISK_DEFAULTS = {
    'stop_loss_percentages': [0.1, 0.2, 0.3, 0.4, 0.5],
    'mae_percentile': 95,  # Percentile for Maximum Adverse Excursion
    'position_size_base': 1.0,
    'max_leverage': 10.0
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'log_dir': 'logs',
    'max_log_files': 10
}

# Performance Monitoring
MONITORING_CONFIG = {
    'status_interval': 100,  # Log status every N data points
    'error_threshold': 10,  # Maximum consecutive errors before alert
    'memory_warning_mb': 500,  # Warning if memory usage exceeds this
}

# Export Settings
EXPORT_CONFIG = {
    'csv_buffer_size': 1,  # Line buffering for CSV (1 = line buffered)
    'compression': False,  # Whether to compress old CSV files
    'backup_interval_hours': 24,  # Auto-backup interval
}