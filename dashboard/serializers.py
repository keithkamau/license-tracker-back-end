from rest_framework import serializers


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics."""
    total_agents = serializers.IntegerField()
    active_agents = serializers.IntegerField()
    inactive_agents = serializers.IntegerField()
    total_licenses = serializers.IntegerField()
    compliance_rate = serializers.FloatField()
    agents_without_licenses = serializers.IntegerField()
    
    license_status = serializers.DictField()
    verification_stats = serializers.DictField()
    expiring_soon_breakdown = serializers.DictField()


class AgentDashboardSerializer(serializers.Serializer):
    """Serializer for agent's personal dashboard."""
    has_license = serializers.BooleanField()
    license_info = serializers.DictField(required=False)
    message = serializers.CharField()
    urgency = serializers.ChoiceField(
        choices=['normal', 'warning', 'critical']
    )


class ComplianceReportSerializer(serializers.Serializer):
    """Serializer for compliance reports."""
    generated_at = serializers.DateTimeField()
    generated_by = serializers.CharField()
    overall_compliance = serializers.DictField()
    expired_licenses = serializers.ListField()
    expiring_soon = serializers.ListField()
    agents_without_licenses = serializers.ListField()