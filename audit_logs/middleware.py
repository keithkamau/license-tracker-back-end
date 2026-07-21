from .models import AuditLog
import json


class AuditLogMiddleware:
    """Middleware to automatically log API requests."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only log authenticated API requests
        if request.user.is_authenticated and request.path.startswith('/api/'):
            self.log_request(request, response)
        
        return response
    
    def log_request(self, request, response):
        """Log the API request."""
        # Skip GET requests except for export and specific views
        if request.method == 'GET' and 'export' not in request.path:
            return
        
        action_map = {
            'POST': AuditLog.Action.CREATE,
            'PUT': AuditLog.Action.UPDATE,
            'PATCH': AuditLog.Action.UPDATE,
            'DELETE': AuditLog.Action.DELETE,
            'GET': AuditLog.Action.VIEW,
        }
        
        action = action_map.get(request.method)
        if not action:
            return
        
        # Determine resource type from URL
        resource_type = self.get_resource_type(request.path)
        
        # Get resource ID if available
        resource_id = self.get_resource_id(request.path)
        
        # Prepare details
        details = {
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
        }
        
        if request.method in ['POST', 'PUT', 'PATCH']:
            # Don't log sensitive data
            safe_data = self.sanitize_data(request.data)
            details['request_data'] = safe_data
        
        AuditLog.objects.create(
            user=request.user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=details,
        )
    
    def get_resource_type(self, path):
        """Extract resource type from URL path."""
        parts = path.strip('/').split('/')
        if len(parts) >= 2 and parts[0] == 'api':
            return parts[1] if len(parts) > 1 else 'unknown'
        return 'unknown'
    
    def get_resource_id(self, path):
        """Extract resource ID from URL path."""
        parts = path.strip('/').split('/')
        # Check if last part is a UUID
        if parts and len(parts[-1]) == 36:
            return parts[-1]
        return None
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def sanitize_data(self, data):
        """Remove sensitive data from request data."""
        if isinstance(data, dict):
            data = data.copy()
            sensitive_fields = ['password', 'password_confirm', 'old_password', 'token']
            for field in sensitive_fields:
                if field in data:
                    data[field] = '***REDACTED***'
        return data