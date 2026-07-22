from django.db import models
from django.core.validators import FileExtensionValidator, MinLengthValidator
from django.utils import timezone
from django.conf import settings
import uuid
import os


def certificate_upload_path(instance, filename):
    """Generate upload path for certificates."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('certificates', str(instance.agent.id), filename)


class License(models.Model):
    """License model for tracking agent IRA certificates."""
    
    class Status(models.TextChoices):
        COMPLIANT = 'compliant', 'Compliant'
        EXPIRING_SOON = 'expiring_soon', 'Expiring Soon'
        EXPIRED = 'expired', 'Expired'
        PENDING = 'pending', 'Pending Verification'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='license'
    )
    license_number = models.CharField(
        max_length=50,
        unique=True,
        validators=[MinLengthValidator(5)]
    )
    issue_date = models.DateField()
    expiry_date = models.DateField(db_index=True)
    certificate_file = models.FileField(
        upload_to=certificate_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'jpg', 'jpeg', 'png']
            )
        ],
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_licenses'
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Notification tracking
    reminder_30_sent = models.BooleanField(default=False)
    reminder_15_sent = models.BooleanField(default=False)
    reminder_7_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'licenses'
        indexes = [
            models.Index(fields=['status', 'expiry_date']),
            models.Index(fields=['agent']),
            models.Index(fields=['license_number']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.agent.get_full_name()} - {self.license_number}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate status based on expiry date
        if self.expiry_date:
            today = timezone.now().date()
            days_until_expiry = (self.expiry_date - today).days
            
            if self.is_verified:
                if days_until_expiry < 0:
                    self.status = self.Status.EXPIRED
                elif days_until_expiry <= 30:
                    self.status = self.Status.EXPIRING_SOON
                else:
                    self.status = self.Status.COMPLIANT
            else:
                self.status = self.Status.PENDING
        
        super().save(*args, **kwargs)
    
    @property
    def days_until_expiry(self):
        """Calculate days remaining until license expiry."""
        if self.expiry_date:
            return (self.expiry_date - timezone.now().date()).days
        return None
    
    @property
    def is_expired(self):
        return self.status == self.Status.EXPIRED
    
    @property
    def is_expiring_soon(self):
        return self.status == self.Status.EXPIRING_SOON


class LicenseAudit(models.Model):
    """Audit trail for license changes."""
    
    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'
        DELETED = 'deleted', 'Deleted'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license = models.ForeignKey(
        License,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    changes = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'license_audits'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} - {self.license.license_number}"