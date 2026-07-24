import django_filters
from .models import License


class LicenseFilter(django_filters.FilterSet):
    """Filter set for licenses with advanced filtering."""
    
    status = django_filters.ChoiceFilter(
        choices=License.Status.choices
    )
    
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search'
    )
    
    expiry_before = django_filters.DateFilter(
        field_name='expiry_date',
        lookup_expr='lte',
        label='Expiry before'
    )
    
    expiry_after = django_filters.DateFilter(
        field_name='expiry_date',
        lookup_expr='gte',
        label='Expiry after'
    )
    
    issue_date_from = django_filters.DateFilter(
        field_name='issue_date',
        lookup_expr='gte'
    )
    
    issue_date_to = django_filters.DateFilter(
        field_name='issue_date',
        lookup_expr='lte'
    )
    
    is_verified = django_filters.BooleanFilter()
    
    agent_email = django_filters.CharFilter(
        field_name='agent__email',
        lookup_expr='icontains'
    )
    
    agent_name = django_filters.CharFilter(
        method='filter_agent_name',
        label='Agent name'
    )
    
    class Meta:
        model = License
        fields = [
            'status', 'is_verified', 'license_number',
            'expiry_before', 'expiry_after'
        ]
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields."""
        from django.db.models import Q
        return queryset.filter(
            Q(license_number__icontains=value) |
            Q(agent__first_name__icontains=value) |
            Q(agent__last_name__icontains=value) |
            Q(agent__email__icontains=value) |
            Q(agent__employee_id__icontains=value)
        )
    
    def filter_agent_name(self, queryset, name, value):
        """Filter by agent's full name."""
        from django.db.models import Q
        return queryset.filter(
            Q(agent__first_name__icontains=value) |
            Q(agent__last_name__icontains=value)
        )