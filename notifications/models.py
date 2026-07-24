from django.db import models
from django.conf import settings
import uuid


class Notification(models.Model):
    """Notification model for system notifications."""
    
    class Type(models.TextChoices):
        LICENSE_EXPIRY = 'license_expiry', 'License Expiry Reminder'
        LICENSE_UPLOADED = 'license_uploaded', 'License Uploaded'
        LICENSE_VERIFIED = 'license_verified', 'License Verified'
        LICENSE_REJECTED = 'license_rejected', 'License Rejected'
        ACCOUNT_CREATED = 'account_created', 'Account Created'
        STATUS_CHANGE = 'status_change', 'Status Change'
    
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(
        max_length=30,
        choices=Type.choices,
        db_index=True
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.user.email}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])


class EmailLog(models.Model):
    """Log for tracking sent emails."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        BOUNCED = 'bounced', 'Bounced'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.EmailField(db_index=True)
    subject = models.CharField(max_length=200)
    template_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING
    )
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'email_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Email to {self.recipient} - {self.subject}"