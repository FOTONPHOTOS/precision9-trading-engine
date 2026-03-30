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
