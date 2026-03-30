#!/bin/bash
# Monitor system logs and block IPs with suspicious activity

LOG_FILE="/var/log/security_monitor_$(date +%Y%m%d).log"

# Function to log events
log_event() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - AUTO_BLOCK: $1" >> $LOG_FILE
}

# Check for IPs making many connections in short time (potential scanners)
netstat -an | grep :80 | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head -20 | while read count ip; do
    if [ $count -gt 50 ] && [ "$ip" != "127.0.0.1" ]; then
        # Check if IP is already blocked
        if ! iptables -L INPUT -v -n | grep -q "$ip"; then
            iptables -A INPUT -s $ip -j DROP
            log_event "Blocked IP $ip for excessive connections ($count connections)"
        fi
    fi
done

# Check authentication logs for failed login attempts (if available)
if [ -f /var/log/auth.log ]; then
    tail -500 /var/log/auth.log | grep "Failed password" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | sort | uniq -c | sort -nr | while read count ip; do
        if [ $count -gt 5 ]; then
            # Check if IP is already blocked
            if ! iptables -L INPUT -v -n | grep -q "$ip"; then
                iptables -A INPUT -s $ip -j DROP
                log_event "Blocked IP $ip for $count failed SSH attempts"
            fi
        fi
    done
fi

log_event "Security monitoring completed at $(date)"
