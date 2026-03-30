# SOL Market Data Collection & Analysis Tool

A comprehensive market data collection and analysis tool for SOL/USDT designed to gather training data for bot calibration and optimization.

## Features

### Data Collection (60+ Metrics)
- **Price Metrics**: Real-time price tracking with changes across multiple timeframes (1s, 5s, 30s, 1m, 5m)
- **CVD Analysis**: Cumulative Volume Delta tracking, velocity, and acceleration
- **Volume Profiling**: Buy/sell volume analysis, trade size distribution, unusual volume detection
- **Order Flow**: Imbalance detection, bid/ask spreads, book depth analysis
- **Market Microstructure**: Tick analysis, VWAP calculations, trade intensity
- **Technical Indicators**: RSI, momentum indicators, volatility measurements
- **Market Regime Detection**: Trending, ranging, volatile state classification
- **Support/Resistance**: Dynamic level calculation and distance tracking

### Data Analysis
- CVD-Price correlation analysis
- Optimal entry/exit condition identification
- Market regime performance analysis
- Risk metrics and position sizing recommendations
- Timing pattern analysis for best trading hours
- Automated calibration report generation

## Quick Start

### 1. Copy to VPS
```bash
# Copy entire directory to your VPS
scp -r SOL_Market_Data_Tool/ user@your-vps:/home/user/
```

### 2. SSH to VPS and Setup
```bash
ssh user@your-vps
cd SOL_Market_Data_Tool

# Make scripts executable
chmod +x setup.sh launch.sh

# Run setup (creates virtual environment and installs dependencies)
./setup.sh
```

### 3. Start Collection
```bash
# Start the collector
./launch.sh start

# Check status
./launch.sh status

# Monitor live output
./launch.sh monitor
```

### 4. Analyze Data (after collection)
```bash
# Run analysis on collected data
./launch.sh analyze
```

## Installation Details

### System Requirements
- Python 3.8 or higher
- 1GB RAM minimum (2GB recommended)
- 10GB disk space for data storage
- Redis server (optional - will use simulation mode if not available)

### Dependencies
All Python dependencies are listed in `requirements.txt` and will be installed automatically by the setup script.

### Manual Installation (if setup.sh doesn't work)
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Launcher Commands
```bash
./launch.sh start    # Start the collector
./launch.sh stop     # Stop the collector
./launch.sh restart  # Restart the collector
./launch.sh status   # Show status and statistics
./launch.sh analyze  # Run analysis on collected data
./launch.sh backup   # Create backup of collected data
./launch.sh clean    # Clean old log files
./launch.sh monitor  # Monitor live collector output
```

### Direct Python Usage
```bash
# Activate virtual environment
source venv/bin/activate

# Run collector
python collector.py  # Uses Redis if available
# OR
python collector_standalone.py  # Works without Redis (simulation mode)

# Run analyzer
python analyzer.py
```

## Configuration

Edit `config.py` to customize:

```python
# Data collection settings
COLLECTION_CONFIG = {
    'symbol': 'SOLUSDT',
    'data_dir': 'sol_training_data',
    'rotation_hours': 6,  # Rotate CSV every 6 hours
    'collection_interval': 1,  # Collect every 1 second
}

# Redis settings (if using)
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
}
```

## Data Files

### Collection Output
- **Location**: `sol_training_data/` directory
- **Format**: CSV files with 60+ columns
- **Rotation**: New file every 6 hours (configurable)
- **Naming**: `sol_market_data_YYYYMMDD_HHMMSS.csv`

### Analysis Output
- **Calibration Report**: `calibration_report_YYYYMMDD_HHMMSS.json`
  - Recommended thresholds for all indicators
  - Optimal entry/exit conditions
  - Risk parameters
  - Trading hour recommendations
- **Visualization**: `analysis_plots_YYYYMMDD_HHMMSS.png`
  - CVD vs Price correlation
  - Success rate analysis
  - Market regime distribution
  - Volatility patterns

## Collected Metrics

### Price & Movement
- Current price and changes (1s to 5m)
- High/Low/Range over timeframes
- Support/Resistance levels

### Volume & Flow
- Volume across timeframes
- Buy/Sell volume separation
- Trade count and size analysis
- Large trade detection
- Dollar volume calculations

### CVD (Cumulative Volume Delta)
- Real-time CVD value
- CVD changes and velocity
- CVD acceleration
- Unusual CVD detection

### Market Structure
- Bid/Ask prices and volumes
- Spread analysis
- Book imbalance
- Order flow imbalance
- VWAP and deviation

### Technical Indicators
- Momentum (1m, 5m, 15m)
- RSI (14-period)
- Volatility measurements
- Trend strength

### Market Conditions
- Regime classification (trending/ranging/volatile)
- Breakout/Breakdown detection
- Accumulation/Distribution phases
- Unusual activity flags

## Monitoring

### Check Collection Status
```bash
./launch.sh status
```
Shows:
- Process status and uptime
- Memory usage
- Number of data points collected
- File sizes and counts
- Recent log entries

### View Live Data
```bash
./launch.sh monitor
# OR
tail -f logs/collector_*.log
```

### Data Statistics
```bash
# Count total data points
wc -l sol_training_data/*.csv

# Check disk usage
du -sh sol_training_data/
```

## Troubleshooting

### Collector Won't Start
1. Check Python version: `python3 --version` (needs 3.8+)
2. Check virtual environment: `source venv/bin/activate`
3. Check dependencies: `pip list`
4. Check logs: `tail -20 logs/collector_*.log`

### No Data Being Collected
1. If using Redis: Check Redis is running: `redis-cli ping`
2. Check Redis data: `redis-cli MONITOR`
3. If no Redis: Collector will use simulation mode automatically

### High Memory Usage
1. Check status: `./launch.sh status`
2. Restart collector: `./launch.sh restart`
3. Adjust `max_history_size` in `config.py`

### Disk Space Issues
1. Check space: `df -h`
2. Backup old data: `./launch.sh backup`
3. Move backups to external storage
4. Clean old logs: `./launch.sh clean`

## Analysis Guide

### Running Analysis
```bash
# After collecting data for 24+ hours
./launch.sh analyze
```

### Understanding Results

#### Calibration Report (JSON)
```json
{
  "cvd_thresholds": {
    "long_entry": 15.2,
    "short_entry": -12.8
  },
  "momentum_thresholds": {
    "long_entry": 0.15,
    "short_entry": -0.12
  },
  "risk_parameters": {
    "stop_loss_pct": 0.3,
    "take_profit_pct": 0.5,
    "base_position_size": 1.5
  }
}
```

#### Using Results for Bot Calibration
1. Update bot thresholds with recommended values
2. Implement regime filters (trade only in favorable regimes)
3. Apply trading hour restrictions
4. Use position sizing recommendations
5. Set stop loss/take profit based on MAE analysis

## Backup & Recovery

### Create Backup
```bash
./launch.sh backup
# Creates: sol_data_backup_YYYYMMDD_HHMMSS.tar.gz
```

### Restore from Backup
```bash
tar -xzf sol_data_backup_*.tar.gz
```

### Transfer Data
```bash
# From VPS to local
scp -r user@vps:/path/to/sol_training_data ./

# Compress before transfer
tar -czf sol_data.tar.gz sol_training_data/
scp user@vps:/path/to/sol_data.tar.gz ./
```

## Performance Tips

### For VPS Deployment
1. Use `screen` or `tmux` for persistent sessions
2. Set up log rotation to prevent disk fill
3. Monitor memory usage regularly
4. Consider using systemd service for auto-restart

### Example systemd Service
Create `/etc/systemd/system/sol-collector.service`:
```ini
[Unit]
Description=SOL Market Data Collector
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/your-user/SOL_Market_Data_Tool
ExecStart=/home/your-user/SOL_Market_Data_Tool/venv/bin/python /home/your-user/SOL_Market_Data_Tool/collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable sol-collector
sudo systemctl start sol-collector
sudo systemctl status sol-collector
```

## Support Files

### Included Files
- `collector.py` - Main collector (requires Redis)
- `collector_standalone.py` - Standalone version (works without Redis)
- `analyzer.py` - Data analysis tool
- `config.py` - Configuration settings
- `requirements.txt` - Python dependencies
- `setup.sh` - Automated setup script
- `launch.sh` - Management launcher script

### Generated Files
- `sol_training_data/*.csv` - Collected market data
- `logs/*.log` - Application logs
- `calibration_report_*.json` - Analysis results
- `analysis_plots_*.png` - Visualization charts
- `collector.pid` - Process ID file

## Notes

- The collector is designed to run continuously for 24+ hours
- CSV files rotate every 6 hours to prevent single file from becoming too large
- Data points are collected every second (configurable)
- The tool can work with or without Redis (simulation mode for testing)
- All timestamps are in UTC

## License

This tool is part of the Precision9 trading system.

---

For issues or questions, refer to the main Precision9 documentation.