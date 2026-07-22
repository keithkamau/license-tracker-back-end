from django.contrib import admin
from .models import License, LicenseAudit


class LicenseAuditInline(admin.TabularInline):
    """Inline admin for license audit logs."""
    model = LicenseAudit
    extra = 0
    readonly_fields = ['action', 'performed_by', 'changes', 'notes', 'created_at']
    can_delete = False
    max_num = 10


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    """Admin configuration for License model."""
    
    list_display = [
        'license_number', 'agent_name', 'status_badge',
        'expiry_date', 'days_until_expiry', 'is_verified',
        'created_at'
    ]
    list_filter = [
        'status', 'is_verified', 'issue_date',
        'expiry_date', 'created_at'
    ]
    search_fields = [
        'license_number', 'agent__email',
        'agent__first_name', 'agent__last_name',
        'agent__employee_id'
    ]
    readonly_fields = [
        'status', 'created_at', 'updated_at',
        'reminder_30_sent', 'reminder_15_sent', 'reminder_7_sent'
    ]
    inlines = [LicenseAuditInline]
    date_hierarchy = 'expiry_date'
    
    fieldsets = (
        ('License Information', {
            'fields': (
                'agent', 'license_number', 'issue_date',
                'expiry_date', 'certificate_file', 'notes'
            )
        }),
        ('Verification Status', {
            'fields': (
                'is_verified', 'verified_by',
                'verification_date', 'status'
            )
        }),
        ('Reminder Status', {
            'fields': (
                'reminder_30_sent', 'reminder_15_sent',
                'reminder_7_sent'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def agent_name(self, obj):
        return obj.agent.get_full_name()
    agent_name.short_description = 'Agent Name'
    agent_name.admin_order_field = 'agent__first_name'
    
    def status_badge(self, obj):
        """Display status with colored badge."""
        colors = {
            'compliant': '#22C55E',
            'expiring_soon': '#F59E0B',
            'expired': '#EF4444',
            'pending': '#6B7280'
        }
        color = colors.get(obj.status, '#6B7280')
        return f'<span style="color: {color}; font-weight: bold;">{obj.get_status_display()}</span>'
    status_badge.short_description = 'Status'
    status_badge.allow_tags = True
    
    def days_until_expiry(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return 'N/A'
        
        if days < 0:
            return f'⚠️ {abs(days)} days ago'
        elif days <= 30:
            return f'⚠️ {days} days'
        return f'{days} days'
    days_until_expiry.short_description = 'Until Expiry'
    
    actions = ['mark_as_verified', 'mark_as_unverified']
    
    def mark_as_verified(self, request, queryset):
        """Admin action to mark licenses as verified."""
        from django.utils import timezone
        updated = queryset.update(
            is_verified=True,
            verified_by=request.user,
            verification_date=timezone.now()
        )
        self.message_user(request, f'{updated} license(s) marked as verified.')
    mark_as_verified.short_description = 'Mark selected licenses as verified'
    
    def mark_as_unverified(self, request, queryset):
        """Admin action to mark licenses as unverified."""
        updated = queryset.update(
            is_verified=False,
            verified_by=None,
            verification_date=None
        )
        self.message_user(request, f'{updated} license(s) marked as unverified.')
    mark_as_unverified.short_description = 'Mark selected licenses as unverified'


@admin.register(LicenseAudit)
class LicenseAuditAdmin(admin.ModelAdmin):
    """Admin configuration for LicenseAudit model."""
    
    list_display = [
        'license_short', 'action_badge', 'performed_by',
        'created_at', 'has_changes'
    ]
    list_filter = ['action', 'created_at']
    search_fields = [
        'license__license_number',
        'performed_by__email',
        'notes'
    ]
    readonly_fields = [
        'license', 'action', 'performed_by',
        'changes', 'notes', 'created_at'
    ]
    date_hierarchy = 'created_at'
    
    def license_short(self, obj):
        return obj.license.license_number[:20]
    license_short.short_description = 'License'
    
    def action_badge(self, obj):
        """Display action with colored badge."""
        colors = {
            'created': '#22C55E',
            'updated': '#027CD0',
            'verified': '#22C55E',
            'rejected': '#EF4444',
            'deleted': '#EF4444'
        }
        color = colors.get(obj.action, '#6B7280')
        return f'<span style="color: {color}; font-weight: 600;">{obj.get_action_display()}</span>'
    action_badge.short_description = 'Action'
    action_badge.allow_tags = True
    
    def has_changes(self, obj):
        return bool(obj.changes)
    has_changes.short_description = 'Has Changes'
    has_changes.boolean = True
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False