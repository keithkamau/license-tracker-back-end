from rest_framework import viewsets, permissions, views
from rest_framework.response import Response
from django.core.cache import cache
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing audit logs (admin only)."""
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Only admin and HR can view audit logs
        if not (user.is_admin or user.is_hr):
            return AuditLog.objects.none()
        
        cache_key = f'audit_logs_{self.request.query_params}'
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        queryset = AuditLog.objects.select_related('user').all()
        
        # Apply filters
        action = self.request.query_params.get('action')
        resource_type = self.request.query_params.get('resource_type')
        user_id = self.request.query_params.get('user_id')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if action:
            queryset = queryset.filter(action=action)
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Cache for 5 minutes
        cache.set(cache_key, queryset, 300)
        
        return queryset