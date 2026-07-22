from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from .models import AuditLog

User = get_user_model()


class AuditLogModelTests(TestCase):
    """Test cases for AuditLog model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='agent@test.com',
            password='TestPass123!',
            first_name='Test',
            last_name='Agent',
            role='agent'
        )
        
        self.audit_log = AuditLog.objects.create(
            user=self.user,
            action='login',
            resource_type='user',
            resource_id=str(self.user.id),
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0',
            details={'method': 'POST'}
        )
    
    def test_audit_log_creation(self):
        """Test audit log creation."""
        self.assertEqual(self.audit_log.user, self.user)
        self.assertEqual(self.audit_log.action, 'login')
        self.assertEqual(self.audit_log.resource_type, 'user')
        self.assertEqual(self.audit_log.ip_address, '127.0.0.1')
    
    def test_audit_log_str_method(self):
        """Test audit log string representation."""
        expected = f"{self.user} - {self.audit_log.action} - {self.audit_log.resource_type}"
        self.assertEqual(str(self.audit_log), expected)
    
    def test_audit_log_choices(self):
        """Test audit log action choices."""
        log = AuditLog.objects.create(
            user=self.user,
            action='create',
            resource_type='license',
            details={'data': 'test'}
        )
        self.assertEqual(log.action, 'create')
        self.assertEqual(log.get_action_display(), 'Create Record')


class AuditLogAPITests(APITestCase):
    """Test cases for AuditLog API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create users
        self.admin = User.objects.create_superuser(
            email='admin@test.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User'
        )
        
        self.agent = User.objects.create_user(
            email='agent@test.com',
            password='AgentPass123!',
            first_name='Test',
            last_name='Agent',
            role='agent'
        )
        
        # Create audit logs
        AuditLog.objects.create(
            user=self.admin,
            action='login',
            resource_type='user',
            resource_id=str(self.admin.id),
            ip_address='127.0.0.1',
            details={'method': 'POST'}
        )
        
        AuditLog.objects.create(
            user=self.agent,
            action='create',
            resource_type='license',
            details={'license_number': 'IRA-12345'}
        )
        
        # Get tokens
        login_url = reverse('token_obtain_pair')
        
        response = self.client.post(login_url, {
            'email': 'admin@test.com',
            'password': 'AdminPass123!'
        })
        self.admin_token = response.data['access']
        
        response = self.client.post(login_url, {
            'email': 'agent@test.com',
            'password': 'AgentPass123!'
        })
        self.agent_token = response.data['access']
    
    def test_list_audit_logs_as_admin(self):
        """Test listing audit logs as admin."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('auditlog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_list_audit_logs_as_agent(self):
        """Test agents cannot access audit logs."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('auditlog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
    
    def test_filter_audit_logs_by_action(self):
        """Test filtering audit logs by action."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('auditlog-list')
        
        response = self.client.get(f'{url}?action=login')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for log in response.data['results']:
            self.assertEqual(log['action'], 'login')
    
    def test_filter_audit_logs_by_resource_type(self):
        """Test filtering audit logs by resource type."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('auditlog-list')
        
        response = self.client.get(f'{url}?resource_type=license')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for log in response.data['results']:
            self.assertEqual(log['resource_type'], 'license')
    
    def test_audit_log_serializer_fields(self):
        """Test audit log serializer includes all fields."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('auditlog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if response.data['results']:
            log = response.data['results'][0]
            self.assertIn('user_name', log)
            self.assertIn('user_email', log)
            self.assertIn('action_display', log)
            self.assertIn('details', log)