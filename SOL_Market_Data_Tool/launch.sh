#!/bin/bash

# SOL Market Data Tool - Launcher Script
# Manages the market data collector process

# Configuration
VENV_PATH="venv"
COLLECTOR_SCRIPT="collector.py"
ANALYZER_SCRIPT="analyzer.py"
LOG_DIR="logs"
DATA_DIR="sol_training_data"
PID_FILE="collector.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create directories if they don't exist
[ ! -d "$LOG_DIR" ] && mkdir -p "$LOG_DIR"
[ ! -d "$DATA_DIR" ] && mkdir -p "$DATA_DIR"

# Function to activate virtual environment
activate_venv() {
    if [ -d "$VENV_PATH" ]; then
        source "$VENV_PATH/bin/activate"
    else
        echo -e "${RED}Virtual environment not found. Run ./setup.sh first${NC}"
        exit 1
    fi
}

# Function to check if collector is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to start the collector
start_collector() {
    if is_running; then
        echo -e "${YELLOW}Collector is already running (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi
    
    activate_venv
    
    LOG_FILE="$LOG_DIR/collector_$(date +%Y%m%d_%H%M%S).log"
    
    echo -e "${GREEN}Starting SOL Market Data Collector...${NC}"
    echo "Log file: $LOG_FILE"
    echo "Data directory: $DATA_DIR"
    
    # Start collector in background
    nohup python "$COLLECTOR_SCRIPT" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    sleep 3
    
    if is_running; then
        echo -e "${GREEN} Collector started successfully (PID: $PID)${NC}"
        echo ""
        echo "Commands:"
        echo "  Monitor logs:  tail -f $LOG_FILE"
        echo "  Check status:  ./launch.sh status"
        echo "  Stop:          ./launch.sh stop"
        return 0
    else
        echo -e "${RED} Failed to start collector${NC}"
        rm -f "$PID_FILE"
        echo "Check log file: $LOG_FILE"
        return 1
    fi
}

# Function to stop the collector
stop_collector() {
    if ! is_running; then
        echo -e "${YELLOW}Collector is not running${NC}"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    echo -e "${YELLOW}Stopping collector (PID: $PID)...${NC}"
    
    # Send SIGTERM for graceful shutdown
    kill -TERM "$PID" 2>/dev/null
    
    # Wait for process to stop
    for i in {1..10}; do
        if ! is_running; then
            break
        fi
        sleep 1
    done
    
    # Force kill if still running
    if is_running; then
        echo -e "${YELLOW}Process didn't stop gracefully, forcing...${NC}"
        kill -9 "$PID" 2>/dev/null
    fi
    
    rm -f "$PID_FILE"
    echo -e "${GREEN} Collector stopped${NC}"
}

# Function to check status
check_status() {
    echo "================================================"
    echo "SOL Market Data Tool - Status"
    echo "================================================"
    echo ""
    
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo -e "Status: ${GREEN}RUNNING${NC}"
        echo "PID: $PID"
        
        # Get process info
        UPTIME=$(ps -o etime= -p "$PID" | xargs)
        echo "Uptime: $UPTIME"
        
        # Check memory usage
        MEM=$(ps -o rss= -p "$PID" | awk '{printf "%.1f", $1/1024}')
        echo "Memory: ${MEM} MB"
    else
        echo -e "Status: ${RED}STOPPED${NC}"
    fi
    
    echo ""
    echo "Data Collection Statistics:"
    echo "----------------------------"
    
    # Check data files
    if [ -d "$DATA_DIR" ]; then
        FILE_COUNT=$(find "$DATA_DIR" -name "*.csv" 2>/dev/null | wc -l)
        
        if [ "$FILE_COUNT" -gt 0 ]; then
            echo "CSV files: $FILE_COUNT"
            
            # Get latest file info
            LATEST_FILE=$(ls -t "$DATA_DIR"/*.csv 2>/dev/null | head -1)
            if [ -f "$LATEST_FILE" ]; then
                SIZE=$(du -h "$LATEST_FILE" | cut -f1)
                LINES=$(wc -l < "$LATEST_FILE")
                MODIFIED=$(stat -c %y "$LATEST_FILE" 2>/dev/null || stat -f %Sm "$LATEST_FILE" 2>/dev/null)
                
                echo "Latest file: $(basename "$LATEST_FILE")"
                echo "  Size: $SIZE"
                echo "  Data points: $((LINES - 1))"
                echo "  Last updated: ${MODIFIED:0:19}"
            fi
            
            # Total data collected
            TOTAL_SIZE=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
            TOTAL_LINES=$(wc -l "$DATA_DIR"/*.csv 2>/dev/null | tail -1 | awk '{print $1}')
            echo ""
            echo "Total data size: $TOTAL_SIZE"
            echo "Total data points: $((TOTAL_LINES - FILE_COUNT))"
        else
            echo "No data files yet"
        fi
    fi
    
    echo ""
    echo "Recent Logs:"
    echo "------------"
    if [ -d "$LOG_DIR" ]; then
        LATEST_LOG=$(ls -t "$LOG_DIR"/collector_*.log 2>/dev/null | head -1)
        if [ -f "$LATEST_LOG" ]; then
            echo "Latest log: $(basename "$LATEST_LOG")"
            echo ""
            tail -5 "$LATEST_LOG"
        fi
    fi
}

# Function to analyze collected data
run_analyzer() {
    activate_venv
    
    echo -e "${GREEN}Running Market Data Analyzer...${NC}"
    echo ""
    
    python "$ANALYZER_SCRIPT"
    
    echo ""
    echo -e "${GREEN}Analysis complete!${NC}"
    echo "Check the $DATA_DIR directory for:"
    echo "  - calibration_report_*.json"
    echo "  - analysis_plots_*.png"
}

# Function to backup data
backup_data() {
    BACKUP_NAME="sol_data_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    echo -e "${YELLOW}Creating backup...${NC}"
    
    tar -czf "$BACKUP_NAME" "$DATA_DIR" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        SIZE=$(du -h "$BACKUP_NAME" | cut -f1)
        echo -e "${GREEN} Backup created: $BACKUP_NAME ($SIZE)${NC}"
    else
        echo -e "${RED} Backup failed${NC}"
    fi
}

# Function to clean old logs
clean_logs() {
    echo -e "${YELLOW}Cleaning old logs...${NC}"
    
    # Keep only last 10 log files
    if [ -d "$LOG_DIR" ]; then
        LOG_COUNT=$(ls -1 "$LOG_DIR"/collector_*.log 2>/dev/null | wc -l)
        if [ "$LOG_COUNT" -gt 10 ]; then
            ls -t "$LOG_DIR"/collector_*.log | tail -n +11 | xargs rm -f
            echo -e "${GREEN} Removed $((LOG_COUNT - 10)) old log files${NC}"
        else
            echo "No old logs to clean"
        fi
    fi
}

# Main script
case "$1" in
    start)
        start_collector
        ;;
    stop)
        stop_collector
        ;;
    restart)
        stop_collector
        sleep 2
        start_collector
        ;;
    status)
        check_status
        ;;
    analyze)
        run_analyzer
        ;;
    backup)
        backup_data
        ;;
    clean)
        clean_logs
        ;;
    monitor)
        if is_running; then
            LATEST_LOG=$(ls -t "$LOG_DIR"/collector_*.log 2>/dev/null | head -1)
            if [ -f "$LATEST_LOG" ]; then
                tail -f "$LATEST_LOG"
            fi
        else
            echo -e "${RED}Collector is not running${NC}"
        fi
        ;;
    *)
        echo "SOL Market Data Tool - Launcher"
        echo "================================"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|analyze|backup|clean|monitor}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the market data collector"
        echo "  stop     - Stop the collector gracefully"
        echo "  restart  - Restart the collector"
        echo "  status   - Show collector status and statistics"
        echo "  analyze  - Run analysis on collected data"
        echo "  backup   - Create backup of collected data"
        echo "  clean    - Clean old log files"
        echo "  monitor  - Monitor live collector output"
        echo ""
        echo "Examples:"
        echo "  $0 start     # Start collecting data"
        echo "  $0 status    # Check collection progress"
        echo "  $0 analyze   # Analyze collected data"
        exit 1
        ;;
esac

exit 0