# dashboard.py
# Simple dashboard module for guard UI compatibility

class SecurityDashboard:
    """Placeholder SecurityDashboard class for guard UI compatibility"""
    
    def __init__(self):
        self.active = False
    
    def start_monitoring(self):
        """Start security monitoring"""
        self.active = True
        print("Security monitoring started")
    
    def stop_monitoring(self):
        """Stop security monitoring"""
        self.active = False
        print("Security monitoring stopped")
    
    def get_status(self):
        """Get current status"""
        return "active" if self.active else "inactive"

