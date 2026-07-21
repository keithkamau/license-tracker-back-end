from rest_framework import serializers
from .models import Notification, EmailLog


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    type_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'type', 'type_display', 'priority',
            'priority_display', 'title', 'message',
            'is_read', 'read_at', 'metadata',
            'created_at', 'time_ago'
        ]
        read_only_fields = [
            'id', 'type', 'priority', 'title',
            'message', 'metadata', 'created_at'
        ]
    
    def get_type_display(self, obj):
        return obj.get_type_display()
    
    def get_priority_display(self, obj):
        return obj.get_priority_display()
    
    def get_time_ago(self, obj):
        """Get human-readable time difference."""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff < timedelta(minutes=1):
            return 'Just now'
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif diff < timedelta(days=30):
            days = diff.days
            return f'{days} day{"s" if days != 1 else ""} ago'
        else:
            return obj.created_at.strftime('%b %d, %Y')


class EmailLogSerializer(serializers.ModelSerializer):
    """Serializer for email logs."""
    
    class Meta:
        model = EmailLog
        fields = [
            'id', 'recipient', 'subject', 'template_name',
            'status', 'error_message', 'sent_at', 'created_at'
        ]
        read_only_fields = fields