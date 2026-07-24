from django.urls import path
from .views import (
    DashboardStatsView,
    AgentDashboardView,
    ComplianceReportView
)

urlpatterns = [
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('agent/', AgentDashboardView.as_view(), name='agent-dashboard'),
    path('report/', ComplianceReportView.as_view(), name='compliance-report'),
]