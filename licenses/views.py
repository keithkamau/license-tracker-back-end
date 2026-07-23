from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q

from .models import License, LicenseAudit
from .serializers import (
    LicenseSerializer,
    LicenseCreateSerializer,
    LicenseUpdateSerializer,
    LicenseVerifySerializer,
    LicenseAuditSerializer
)
from .permissions import IsLicenseOwnerOrAdmin, CanUploadLicense, CanVerifyLicense
from .filters import LicenseFilter


class LicenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing agent licenses.
    Provides CRUD operations with role-based access control.
    """
    queryset = License.objects.select_related('agent').all()  # Add default queryset
    filterset_class = LicenseFilter
    parser_classes = [MultiPartParser, FormParser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LicenseCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return LicenseUpdateSerializer
        return LicenseSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), CanUploadLicense()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsLicenseOwnerOrAdmin()]
        elif self.action == 'verify':
            return [permissions.IsAuthenticated(), CanVerifyLicense()]
        return [permissions.IsAuthenticated(), IsLicenseOwnerOrAdmin()]
    
    def get_queryset(self):
        user = self.request.user
        cache_key = f'license_queryset_{user.id}_{user.role}'
        
        # Try cache first
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        
        queryset = License.objects.select_related('agent').all()
        
        # Agents can only see their own license
        if user.is_agent:
            queryset = queryset.filter(agent=user)
        
        # Cache for 2 minutes
        cache.set(cache_key, queryset, 120)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """List licenses with filtering and statistics."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get statistics
        stats = queryset.aggregate(
            total=Count('id'),
            compliant=Count('id', filter=Q(status='compliant')),
            expiring_soon=Count('id', filter=Q(status='expiring_soon')),
            expired=Count('id', filter=Q(status='expired')),
            pending=Count('id', filter=Q(status='pending')),
        )
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['statistics'] = stats
            return response
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'statistics': stats
        })
    
    def create(self, request, *args, **kwargs):
        """Create a new license with audit trail."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            # Set the agent to current user if agent
            if request.user.is_agent:
                serializer.validated_data['agent'] = request.user
            
            license = serializer.save()
            
            # Create audit log
            LicenseAudit.objects.create(
                license=license,
                action=LicenseAudit.Action.CREATED,
                performed_by=request.user,
                notes='License created'
            )
            
            # Invalidate cache
            cache.delete_pattern('license_*')
            cache.delete_pattern('dashboard_*')
        
        return Response(
            LicenseSerializer(license, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Update license with change tracking."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_data = LicenseSerializer(instance).data
        
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            license = serializer.save()
            
            # Track changes
            changes = {}
            for field in ['license_number', 'issue_date', 'expiry_date', 'notes']:
                if field in serializer.validated_data:
                    old_value = old_data.get(field)
                    new_value = serializer.validated_data[field]
                    if str(old_value) != str(new_value):
                        changes[field] = {
                            'old': str(old_value),
                            'new': str(new_value)
                        }
            
            if changes:
                LicenseAudit.objects.create(
                    license=license,
                    action=LicenseAudit.Action.UPDATED,
                    performed_by=request.user,
                    changes=changes,
                    notes=f'Updated fields: {", ".join(changes.keys())}'
                )
            
            # Invalidate cache
            cache.delete_pattern('license_*')
            cache.delete_pattern('dashboard_*')
        
        return Response(LicenseSerializer(license, context={'request': request}).data)
    
    @action(detail=True, methods=['POST'])
    def verify(self, request, pk=None):
        """Verify or reject a license."""
        license = self.get_object()
        serializer = LicenseVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            license.is_verified = serializer.validated_data['is_verified']
            license.verified_by = request.user
            license.verification_date = timezone.now()
            
            if not license.is_verified:
                license.status = License.Status.PENDING
            
            if 'notes' in serializer.validated_data:
                license.notes = serializer.validated_data['notes']
            
            license.save()
            
            # Create audit log
            action = LicenseAudit.Action.VERIFIED if license.is_verified else LicenseAudit.Action.REJECTED
            LicenseAudit.objects.create(
                license=license,
                action=action,
                performed_by=request.user,
                notes=serializer.validated_data.get('notes', '')
            )
            
            # Invalidate cache
            cache.delete_pattern('license_*')
            cache.delete_pattern('dashboard_*')
        
        return Response(LicenseSerializer(license, context={'request': request}).data)
    
    @action(detail=False, methods=['GET'])
    def export_csv(self, request):
        """Export licenses as CSV."""
        import csv
        from django.http import HttpResponse
        
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filter for pending renewal if specified
        if request.query_params.get('pending_renewal'):
            queryset = queryset.filter(status__in=['expiring_soon', 'expired'])
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="licenses_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Agent Name', 'Email', 'Employee ID', 'License Number',
            'Issue Date', 'Expiry Date', 'Status', 'Days Until Expiry',
            'Verified'
        ])
        
        for license in queryset:
            writer.writerow([
                license.agent.get_full_name(),
                license.agent.email,
                license.agent.employee_id or '',
                license.license_number,
                license.issue_date,
                license.expiry_date,
                license.get_status_display(),
                license.days_until_expiry,
                'Yes' if license.is_verified else 'No'
            ])
        
        return response
    
    @action(detail=True, methods=['GET'])
    def audit_log(self, request, pk=None):
        """Get audit logs for a specific license."""
        license = self.get_object()
        logs = LicenseAudit.objects.filter(license=license)
        serializer = LicenseAuditSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['GET'])
    def statistics(self, request):
        """Get comprehensive license statistics."""
        cache_key = f'license_stats_{request.user.id}'
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return Response(cached_stats)
        
        base_queryset = self.get_queryset()
        
        stats = {
            'total': base_queryset.count(),
            'by_status': {
                'compliant': base_queryset.filter(status='compliant').count(),
                'expiring_soon': base_queryset.filter(status='expiring_soon').count(),
                'expired': base_queryset.filter(status='expired').count(),
                'pending': base_queryset.filter(status='pending').count(),
            },
            'verified': base_queryset.filter(is_verified=True).count(),
            'unverified': base_queryset.filter(is_verified=False).count(),
            'expiring_in_30_days': base_queryset.filter(
                status='expiring_soon',
                expiry_date__lte=timezone.now().date() + timezone.timedelta(days=30)
            ).count(),
            'expiring_in_7_days': base_queryset.filter(
                status='expiring_soon',
                expiry_date__lte=timezone.now().date() + timezone.timedelta(days=7)
            ).count(),
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, stats, 300)
        
        return Response(stats)