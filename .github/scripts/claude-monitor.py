#!/usr/bin/env python3
"""
Claude Monitoring Script
Tracks usage, costs, and security events for Claude integration
"""

import json
import os
import sys
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/claude-monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class ClaudeMonitor:
    def __init__(self, config_path='.github/claude-config.yml'):
        self.config_path = config_path
        self.metrics_file = '/tmp/claude-metrics.json'
        self.load_config()
    
    def load_config(self):
        """Load configuration from YAML file"""
        # Simplified config loading - in production would use PyYAML
        self.config = {
            'thresholds': {
                'cost_per_hour': 10.0,
                'requests_per_minute': 5,
                'failed_requests_threshold': 3
            },
            'monitoring': {
                'track_costs': True,
                'detect_abuse': True,
                'log_metrics': True,
                'enable_alerts': True
            }
        }
    
    def load_metrics(self):
        """Load existing metrics from file"""
        if not os.path.exists(self.metrics_file):
            return {
                'requests': [],
                'costs': [],
                'failures': [],
                'users': {}
            }
        
        try:
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load metrics: {e}")
            return {'requests': [], 'costs': [], 'failures': [], 'users': {}}
    
    def save_metrics(self, metrics):
        """Save metrics to file"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def record_request(self, user, event_type, success=True, cost=0.0):
        """Record a Claude request"""
        metrics = self.load_metrics()
        timestamp = datetime.now().isoformat()
        
        # Record request
        request_record = {
            'timestamp': timestamp,
            'user': user,
            'event_type': event_type,
            'success': success,
            'cost': cost
        }
        
        metrics['requests'].append(request_record)
        
        # Update user stats
        if user not in metrics['users']:
            metrics['users'][user] = {
                'total_requests': 0,
                'failed_requests': 0,
                'total_cost': 0.0,
                'last_request': timestamp
            }
        
        metrics['users'][user]['total_requests'] += 1
        metrics['users'][user]['total_cost'] += cost
        metrics['users'][user]['last_request'] = timestamp
        
        if not success:
            metrics['users'][user]['failed_requests'] += 1
            metrics['failures'].append(request_record)
        
        if cost > 0:
            metrics['costs'].append({
                'timestamp': timestamp,
                'user': user,
                'cost': cost
            })
        
        self.save_metrics(metrics)
        logger.info(f"Recorded request: {user} -> {event_type} (${cost:.4f})")
        
        # Check for alerts
        self.check_alerts(metrics, user)
    
    def check_alerts(self, metrics, user):
        """Check if any alert thresholds are breached"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        minute_ago = now - timedelta(minutes=1)
        
        # Check cost per hour
        hourly_cost = sum(
            record['cost'] for record in metrics['costs']
            if datetime.fromisoformat(record['timestamp']) > hour_ago
        )
        
        if hourly_cost > self.config['thresholds']['cost_per_hour']:
            logger.warning(f"🚨 ALERT: Hourly cost threshold breached: ${hourly_cost:.2f}")
        
        # Check requests per minute
        recent_requests = len([
            record for record in metrics['requests']
            if datetime.fromisoformat(record['timestamp']) > minute_ago
        ])
        
        if recent_requests > self.config['thresholds']['requests_per_minute']:
            logger.warning(f"🚨 ALERT: Request rate threshold breached: {recent_requests} requests/min")
        
        # Check failed requests for user
        user_failed = metrics['users'][user]['failed_requests']
        if user_failed >= self.config['thresholds']['failed_requests_threshold']:
            logger.warning(f"🚨 ALERT: User {user} has {user_failed} failed requests")
    
    def get_usage_summary(self):
        """Get usage summary for the last 24 hours"""
        metrics = self.load_metrics()
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        
        recent_requests = [
            record for record in metrics['requests']
            if datetime.fromisoformat(record['timestamp']) > day_ago
        ]
        
        total_requests = len(recent_requests)
        successful_requests = len([r for r in recent_requests if r['success']])
        total_cost = sum(record.get('cost', 0) for record in recent_requests)
        
        unique_users = len(set(record['user'] for record in recent_requests))
        
        summary = {
            'period': '24 hours',
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            'total_cost': total_cost,
            'unique_users': unique_users,
            'average_cost_per_request': (total_cost / total_requests) if total_requests > 0 else 0
        }
        
        return summary
    
    def cleanup_old_metrics(self, days=7):
        """Remove metrics older than specified days"""
        metrics = self.load_metrics()
        cutoff = datetime.now() - timedelta(days=days)
        
        # Filter out old records
        for key in ['requests', 'costs', 'failures']:
            metrics[key] = [
                record for record in metrics[key]
                if datetime.fromisoformat(record['timestamp']) > cutoff
            ]
        
        self.save_metrics(metrics)
        logger.info(f"Cleaned up metrics older than {days} days")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python claude-monitor.py <command> [args...]")
        print("Commands:")
        print("  record <user> <event_type> [success] [cost]")
        print("  summary")
        print("  cleanup [days]")
        sys.exit(1)
    
    monitor = ClaudeMonitor()
    command = sys.argv[1]
    
    if command == 'record':
        if len(sys.argv) < 4:
            print("Usage: record <user> <event_type> [success] [cost]")
            sys.exit(1)
        
        user = sys.argv[2]
        event_type = sys.argv[3]
        success = sys.argv[4].lower() == 'true' if len(sys.argv) > 4 else True
        cost = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
        
        monitor.record_request(user, event_type, success, cost)
    
    elif command == 'summary':
        summary = monitor.get_usage_summary()
        print(json.dumps(summary, indent=2))
    
    elif command == 'cleanup':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        monitor.cleanup_old_metrics(days)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()