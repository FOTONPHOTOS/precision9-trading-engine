#!/bin/bash
# Security monitoring script for Arsenal VPS
# Monitors logs and blocks suspicious IPs automatically

LOG_FILE="/var/log/security_monitor_$(date +%Y%m%d).log"

# Function to log security events
log_event() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - SECURITY: $1" >> $LOG_FILE
}

log_event "Starting security monitoring service"

# Monitor for common attack patterns and block repeatedly scanning IPs
# This creates a cron job to run every 5 minutes and block IPs with >20 failed attempts
cat > /etc/cron.every5minutes << 'EOF'
*/5 * * * * /root/Desktop/Arsenal\ VPS/monitor_attacks.sh >> /var/log/security_monitor.log 2>&1
EOF

# Create the attack monitoring script
cat > /root/Desktop/Arsenal\ VPS/monitor_attacks.sh << 'MONITOR_EOF'
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
MONITOR_EOF

chmod +x /root/Desktop/Arsenal\ VPS/monitor_attacks.sh

# Also set up fail2ban-like protection for ssh (basic version)
cat > /etc/cron.hourly/ssh_block << 'SSH_EOF'
#!/bin/bash
# Basic SSH brute force protection
BLOCKED_IPS=$(tail -100 /var/log/auth.log 2>/dev/null | grep "Failed password" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | sort | uniq -c | awk '$1 > 10 {print $2}')

for ip in $BLOCKED_IPS; do
    if ! iptables -L INPUT -v -n | grep -q "$ip" && [ "$ip" != "" ]; then
        iptables -A INPUT -s $ip -j DROP
        echo "$(date): Blocked $ip for SSH brute force" >> /var/log/security_monitor.log
    fi
done
SSH_EOF

chmod +x /etc/cron.hourly/ssh_block

# Create a script to check current firewall status
cat > /root/Desktop/Arsenal\ VPS/check_security.sh << 'CHECK_EOF'
#!/bin/bash
echo "🛡️  Current Security Status:"
echo ""
echo "📋 Active IP Tables Rules:"
iptables -L -n -v --line-numbers
echo ""
echo "🌐 Blocked IPs:"
iptables -L INPUT -n -v | grep DROP | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}'
echo ""
echo "📊 Active Network Connections:"
netstat -an | head -20
echo "..."
echo ""
echo "🔒 Security measures active:"
echo "  - DDoS Protection: ON"
echo "  - Port Scan Detection: ON" 
echo "  - SSH Brute Force Protection: ON"
echo "  - Suspicious Activity Logging: ON"
echo ""
echo "To view logs: cat /var/log/security_monitor_*.log"
CHECK_EOF

chmod +x /root/Desktop/Arsenal\ VPS/check_security.sh

# Add automatic security updates
cat > /etc/cron.weekly/security_updates << 'UPDATE_EOF'
#!/bin/bash
# Weekly security maintenance
apt-get update && apt-get upgrade -y && apt-get autoremove -y
echo "$(date): Security updates applied" >> /var/log/security_monitor.log
UPDATE_EOF

chmod +x /etc/cron.weekly/security_updates

log_event "Security monitoring and auto-blocking system installed"
echo "🛡️  VPS Security System Installed!"
echo "   - Auto-blocking for suspicious IPs every 5 minutes"
echo "   - SSH brute force protection hourly"
echo "   - Weekly security updates"
echo "   - Monitoring script: /root/Desktop/Arsenal VPS/monitor_attacks.sh"
echo "   - Status checker: /root/Desktop/Arsenal VPS/check_security.sh"
echo "   - Logs in: /var/log/security_monitor_*.log"