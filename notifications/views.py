from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notifications."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return notifications for the current user."""
        user = self.request.user
        queryset = Notification.objects.filter(user=user)
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read', None)
        if is_read is not None:
            is_read = is_read.lower() == 'true'
            queryset = queryset.filter(is_read=is_read)
        
        # Filter by type
        notification_type = self.request.query_params.get('type', None)
        if notification_type:
            queryset = queryset.filter(type=notification_type)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """List notifications with unread count."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get unread count
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['unread_count'] = unread_count
            return response
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'unread_count': unread_count
        })
    
    @action(detail=False, methods=['POST'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        from django.utils import timezone
        
        updated = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        # Clear notification cache
        cache.delete_pattern(f'notifications_{request.user.id}_*')
        
        return Response({
            'message': f'{updated} notifications marked as read',
            'updated_count': updated
        })
    
    @action(detail=True, methods=['POST'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = get_object_or_404(
            Notification,
            id=pk,
            user=request.user
        )
        notification.mark_as_read()
        
        return Response({
            'message': 'Notification marked as read'
        })
    
    @action(detail=False, methods=['GET'])
    def unread_count(self, request):
        """Get count of unread notifications."""
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        return Response({
            'unread_count': count
        })