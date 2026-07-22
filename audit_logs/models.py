from django.db import models
from django.conf import settings
import uuid


class AuditLog(models.Model):
    """Audit log for tracking user actions across the system."""
    
    class Action(models.TextChoices):
        LOGIN = 'login', 'User Login'
        LOGOUT = 'logout', 'User Logout'
        CREATE = 'create', 'Create Record'
        UPDATE = 'update', 'Update Record'
        DELETE = 'delete', 'Delete Record'
        VIEW = 'view', 'View Record'
        EXPORT = 'export', 'Export Data'
        UPLOAD = 'upload', 'Upload File'
        STATUS_CHANGE = 'status_change', 'Status Change'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    resource_type = models.CharField(max_length=50, db_index=True)
    resource_id = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.resource_type}"