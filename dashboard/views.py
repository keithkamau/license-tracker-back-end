from rest_framework import views, permissions
from rest_framework.response import Response
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q, Sum, Avg
from django.db.models.functions import TruncMonth, ExtractMonth
from datetime import timedelta

from licenses.models import License
from accounts.models import User


class DashboardStatsView(views.APIView):
    """Dashboard statistics for admin and HR."""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Only admin and HR can see full dashboard
        if not (user.is_admin or user.is_hr):
            return Response({
                'error': 'Access denied'
            }, status=403)
        
        cache_key = 'dashboard_stats'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        today = timezone.now().date()
        thirty_days_from_now = today + timedelta(days=30)
        
        # Agent statistics
        total_agents = User.objects.filter(role='agent').count()
        active_agents = User.objects.filter(role='agent', is_active=True).count()
        inactive_agents = User.objects.filter(role='agent', is_active=False).count()
        
        # License statistics
        licenses = License.objects.all()
        total_licenses = licenses.count()
        
        license_stats = licenses.aggregate(
            compliant=Count('id', filter=Q(status='compliant')),
            expiring_soon=Count('id', filter=Q(status='expiring_soon')),
            expired=Count('id', filter=Q(status='expired')),
            pending=Count('id', filter=Q(status='pending')),
            verified=Count('id', filter=Q(is_verified=True)),
            unverified=Count('id', filter=Q(is_verified=False)),
        )
        
        # Calculate percentages
        compliance_rate = (
            (license_stats['compliant'] / total_licenses * 100)
            if total_licenses > 0 else 0
        )
        
        # Expiring soon breakdown
        expiring_in_7_days = licenses.filter(
            status='expiring_soon',
            expiry_date__lte=today + timedelta(days=7)
        ).count()
        
        expiring_in_15_days = licenses.filter(
            status='expiring_soon',
            expiry_date__lte=today + timedelta(days=15),
            expiry_date__gt=today + timedelta(days=7)
        ).count()
        
        expiring_in_30_days = licenses.filter(
            status='expiring_soon',
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gt=today + timedelta(days=15)
        ).count()
        
        # Monthly trends (last 6 months)
        six_months_ago = today - timedelta(days=180)
        monthly_trends = (
            License.objects
            .filter(created_at__gte=six_months_ago)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                total=Count('id'),
                new_licenses=Count('id', filter=Q(action='created'))
            )
            .order_by('month')
        )
        
        # Agents without licenses
        agents_without_licenses = (
            User.objects
            .filter(role='agent', is_active=True)
            .exclude(license__isnull=False)
            .count()
        )
        
        # Recently updated licenses
        recent_updates = (
            License.objects
            .select_related('agent')
            .order_by('-updated_at')[:5]
            .values(
                'id', 'license_number',
                'agent__first_name', 'agent__last_name',
                'status', 'updated_at'
            )
        )
        
        data = {
            'summary': {
                'total_agents': total_agents,
                'active_agents': active_agents,
                'inactive_agents': inactive_agents,
                'total_licenses': total_licenses,
                'compliance_rate': round(compliance_rate, 2),
                'agents_without_licenses': agents_without_licenses,
            },
            'license_status': {
                'compliant': license_stats['compliant'],
                'expiring_soon': license_stats['expiring_soon'],
                'expired': license_stats['expired'],
                'pending': license_stats['pending'],
            },
            'verification_stats': {
                'verified': license_stats['verified'],
                'unverified': license_stats['unverified'],
                'verification_rate': (
                    (license_stats['verified'] / total_licenses * 100)
                    if total_licenses > 0 else 0
                ),
            },
            'expiring_soon_breakdown': {
                'within_7_days': expiring_in_7_days,
                'within_15_days': expiring_in_15_days,
                'within_30_days': expiring_in_30_days,
            },
            'monthly_trends': list(monthly_trends),
            'recent_updates': list(recent_updates),
            'last_updated': timezone.now().isoformat(),
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, data, 300)
        
        return Response(data)


class AgentDashboardView(views.APIView):
    """Personal dashboard for agents."""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if not user.is_agent:
            return Response({
                'error': 'This dashboard is for agents only'
            }, status=403)
        
        try:
            license = License.objects.get(agent=user)
            
            data = {
                'has_license': True,
                'license_info': {
                    'license_number': license.license_number,
                    'status': license.status,
                    'status_display': license.get_status_display(),
                    'issue_date': license.issue_date,
                    'expiry_date': license.expiry_date,
                    'days_until_expiry': license.days_until_expiry,
                    'is_verified': license.is_verified,
                },
                'reminders': {
                    'next_reminder_in_days': min(
                        [d for d in [30, 15, 7] if not getattr(license, f'reminder_{d}_sent')],
                        default=None
                    ),
                }
            }
            
            # Add urgency level
            days = license.days_until_expiry
            if days and days <= 7:
                data['license_info']['urgency'] = 'critical'
                data['message'] = 'Your license expires very soon! Please renew immediately.'
            elif days and days <= 30:
                data['license_info']['urgency'] = 'warning'
                data['message'] = 'Your license is expiring soon. Please prepare for renewal.'
            else:
                data['license_info']['urgency'] = 'normal'
                data['message'] = 'Your license is up to date.'
            
            return Response(data)
            
        except License.DoesNotExist:
            return Response({
                'has_license': False,
                'message': 'You have not uploaded your license yet. Please upload your IRA certificate.',
                'urgency': 'critical'
            })


class ComplianceReportView(views.APIView):
    """Generate compliance reports."""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if not (user.is_admin or user.is_hr):
            return Response({'error': 'Access denied'}, status=403)
        
        today = timezone.now().date()
        
        # Generate report
        report = {
            'generated_at': timezone.now().isoformat(),
            'generated_by': user.get_full_name(),
            'overall_compliance': {
                'total_agents': User.objects.filter(role='agent').count(),
                'compliant_agents': License.objects.filter(status='compliant').count(),
                'non_compliant_agents': License.objects.filter(
                    status__in=['expired', 'pending']
                ).count(),
            },
            'expired_licenses': list(
                License.objects
                .filter(status='expired')
                .select_related('agent')
                .values(
                    'agent__first_name',
                    'agent__last_name',
                    'agent__email',
                    'license_number',
                    'expiry_date'
                )
            ),
            'expiring_soon': list(
                License.objects
                .filter(
                    status='expiring_soon',
                    expiry_date__lte=today + timedelta(days=30)
                )
                .select_related('agent')
                .values(
                    'agent__first_name',
                    'agent__last_name',
                    'agent__email',
                    'license_number',
                    'expiry_date'
                )
                .order_by('expiry_date')
            ),
            'agents_without_licenses': list(
                User.objects
                .filter(role='agent', is_active=True)
                .exclude(license__isnull=False)
                .values('first_name', 'last_name', 'email', 'employee_id')
            ),
        }
        
        return Response(report)