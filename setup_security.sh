#!/bin/bash
# Comprehensive security configuration for Arsenal VPS
# Sets up firewall rules and security measures to protect against attacks

echo "  Setting up comprehensive VPS security..."

# Create backup of current iptables
iptables-save > /root/iptables_backup_before_security_setup_$(date +%Y%m%d_%H%M%S).rules

# 1. Basic Firewall Configuration
echo " Setting up basic firewall rules..."

# Flush existing rules
iptables -F
iptables -X

# Set default policies to DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow loopback traffic
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established and related connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (important for remote access) - adjust port if needed
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow your trading system ports
iptables -A INPUT -p tcp --dport 8765 -j ACCEPT  # Aegis WebSocket
iptables -A INPUT -p tcp --dport 8009 -j ACCEPT # Dashboard WebSocket
iptables -A INPUT -p tcp --dport 8000:9000 -j ACCEPT  # General app ports

# Allow HTTP and HTTPS for API calls (needed for trading)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# 2. Rate limiting to prevent flooding
echo " Implementing rate limiting..."

# Limit SSH brute force attempts
iptables -A INPUT -p tcp --dport 22 -m limit --limit 3/min --limit-burst 5 -j ACCEPT

# SYN flood protection
iptables -A INPUT -p tcp --tcp-flags SYN,ACK,FIN,RST SYN -m limit --limit 2/s --limit-burst 10 -j ACCEPT

# 3. Block known malicious IPs (including the one we already blocked)
echo " Adding IP blocks..."

# Block the scanner IP we identified
iptables -A INPUT -s 172.235.168.35 -j DROP

# Block private networks that shouldn't be connecting externally
iptables -A INPUT -s 10.0.0.0/8 -j DROP
iptables -A INPUT -s 172.16.0.0/12 -j DROP  
iptables -A INPUT -s 192.168.0.0/16 -j DROP
iptables -A INPUT -s 127.0.0.0/8 -j DROP

# 4. Enable connection tracking for better security
echo " Enabling connection tracking..."

# Load required modules
modprobe ip_conntrack
modprobe ip_conntrack_ftp

# 5. Log suspicious activities
echo " Setting up logging for suspicious activities..."

# Create custom chain for logging suspicious packets
iptables -N LOGGING

# Log and drop invalid packets
iptables -A INPUT -m conntrack --ctstate INVALID -j LOG --log-prefix "INVALID_PACKET: " --log-level 4
iptables -A INPUT -m conntrack --ctstate INVALID -j DROP

# Log packets that reach end of rules (suspicious)
iptables -A INPUT -j LOGGING
iptables -A LOGGING -j LOG --log-prefix "DROPPED_PACKET: " --log-level 4
iptables -A LOGGING -j DROP

# 6. Block common attack patterns
echo "  Blocking common attack patterns..."

# Block NULL packets
iptables -A INPUT -p tcp --tcp-flags ALL NONE -j DROP

# Block XMAS packets  
iptables -A INPUT -p tcp --tcp-flags ALL ALL -j DROP

# Block syn-flood attacks
iptables -A INPUT -p tcp --syn -m limit --limit 1/s --limit-burst 3 -j RETURN
iptables -A INPUT -p tcp --syn -j DROP

# 7. DDOS protection
echo "  Adding DDoS protection..."

# Limit ICMP (ping) floods
iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/s -j ACCEPT
iptables -A INPUT -p icmp --icmp-type echo-request -j DROP

# 8. Port scanning detection
echo " Adding port scan detection..."

# Log port scans (scans of 10+ ports)
iptables -A INPUT -p tcp --tcp-flags FIN,SYN,RST,ACK SYN -m connlimit --connlimit-above 100 -j LOG --log-prefix "PORTSCAN: "
iptables -A INPUT -p tcp --tcp-flags FIN,SYN,RST,ACK SYN -m connlimit --connlimit-above 100 -j DROP

# Save the rules
echo " Saving iptables rules..."
iptables-save > /etc/iptables/rules.v4

# Display summary
echo ""
echo "  Security setup complete!"
echo ""
echo " Current firewall rules:"
iptables -L -n -v
echo ""
echo "  Protection includes:"
echo "   - Rate limiting for SSH and other connections"
echo "   - Blocking of private networks"
echo "   - DDoS protection"
echo "   - Port scan detection"
echo "   - SYN flood protection"
echo "   - Logging of suspicious activity"
echo "   - Block of malicious IP: 172.235.168.35"
echo ""
echo "  Important: Make sure you can still SSH into your VPS after these changes!"
echo "   If you lose access, contact your VPS provider for console access."

# Test connectivity
echo ""
echo " Testing basic connectivity..."
echo "Localhost: $(ping -c 1 -W 2 127.0.0.1 > /dev/null 2>&1 && echo 'OK' || echo 'FAILED')"
echo "Gateway ping test: $(ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1 && echo 'OK' || echo 'FAILED')"