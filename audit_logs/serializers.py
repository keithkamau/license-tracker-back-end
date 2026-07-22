from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs."""
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'user_email',
            'action', 'action_display', 'resource_type',
            'resource_id', 'ip_address', 'details',
            'created_at'
        ]
    
    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return 'System'
    
    def get_user_email(self, obj):
        if obj.user:
            return obj.user.email
        return None
    
    def get_action_display(self, obj):
        return obj.get_action_display()