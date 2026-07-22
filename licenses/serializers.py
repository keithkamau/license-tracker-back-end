from rest_framework import serializers
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from .models import License, LicenseAudit


class LicenseSerializer(serializers.ModelSerializer):
    """Serializer for license data."""
    agent_name = serializers.SerializerMethodField()
    agent_email = serializers.SerializerMethodField()
    days_until_expiry = serializers.IntegerField(read_only=True)
    certificate_url = serializers.SerializerMethodField()
    
    class Meta:
        model = License
        fields = [
            'id', 'agent', 'agent_name', 'agent_email',
            'license_number', 'issue_date', 'expiry_date',
            'status', 'is_verified', 'certificate_file',
            'certificate_url', 'days_until_expiry',
            'reminder_30_sent', 'reminder_15_sent', 'reminder_7_sent',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'is_verified', 'created_at',
            'updated_at', 'reminder_30_sent', 'reminder_15_sent',
            'reminder_7_sent'
        ]
    
    def get_agent_name(self, obj):
        return obj.agent.get_full_name()
    
    def get_agent_email(self, obj):
        return obj.agent.email
    
    def get_certificate_url(self, obj):
        if obj.certificate_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.certificate_file.url)
            return obj.certificate_file.url
        return None
    
    def validate_expiry_date(self, value):
        """Ensure expiry date is after issue date."""
        issue_date = self.initial_data.get('issue_date')
        if issue_date:
            from datetime import datetime
            issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
            if value <= issue_date:
                raise serializers.ValidationError(
                    'Expiry date must be after issue date.'
                )
        
        if value < timezone.now().date():
            raise serializers.ValidationError(
                'Expiry date cannot be in the past.'
            )
        
        return value
    
    def validate_certificate_file(self, value):
        """Validate file size and type."""
        if value:
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if value.size > max_size:
                raise serializers.ValidationError(
                    'File size must be less than 10MB.'
                )
            
            # Check file extension
            allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
            ext = value.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise serializers.ValidationError(
                    f'File type not allowed. Allowed types: {", ".join(allowed_extensions)}'
                )
        
        return value


class LicenseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new licenses."""
    
    class Meta:
        model = License
        fields = [
            'agent', 'license_number', 'issue_date',
            'expiry_date', 'certificate_file', 'notes'
        ]
    
    def validate_license_number(self, value):
        """Check if license number already exists."""
        if License.objects.filter(license_number=value).exists():
            raise serializers.ValidationError(
                'A license with this number already exists.'
            )
        return value
    
    def validate_agent(self, value):
        """Check if agent already has a license."""
        if License.objects.filter(agent=value).exists():
            raise serializers.ValidationError(
                'This agent already has a license registered.'
            )
        return value


class LicenseUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating licenses."""
    
    class Meta:
        model = License
        fields = [
            'license_number', 'issue_date', 'expiry_date',
            'certificate_file', 'notes', 'is_verified'
        ]


class LicenseVerifySerializer(serializers.Serializer):
    """Serializer for verifying licenses."""
    is_verified = serializers.BooleanField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class LicenseAuditSerializer(serializers.ModelSerializer):
    """Serializer for license audit logs."""
    performed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = LicenseAudit
        fields = [
            'id', 'action', 'performed_by', 'performed_by_name',
            'changes', 'notes', 'created_at'
        ]
    
    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name()
        return None