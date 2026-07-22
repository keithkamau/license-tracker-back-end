from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from licenses.models import License

User = get_user_model()


class DashboardAPITests(APITestCase):
    """Test cases for Dashboard API endpoints."""
    
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
        
        self.hr = User.objects.create_user(
            email='hr@test.com',
            password='HrPass123!',
            first_name='HR',
            last_name='User',
            role='hr'
        )
        
        # Create license for agent
        self.license = License.objects.create(
            agent=self.agent,
            license_number='IRA-12345-2024',
            issue_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timedelta(days=365),
            is_verified=True
        )
        
        # Create agents with different license statuses
        self.agent_expired = User.objects.create_user(
            email='expired@test.com',
            password='TestPass123!',
            first_name='Expired',
            last_name='Agent',
            role='agent'
        )
        
        License.objects.create(
            agent=self.agent_expired,
            license_number='IRA-EXPIRED-2024',
            issue_date=timezone.now().date() - timedelta(days=400),
            expiry_date=timezone.now().date() - timedelta(days=10),
            is_verified=True
        )
        
        self.agent_expiring = User.objects.create_user(
            email='expiring@test.com',
            password='TestPass123!',
            first_name='Expiring',
            last_name='Agent',
            role='agent'
        )
        
        License.objects.create(
            agent=self.agent_expiring,
            license_number='IRA-EXPIRING-2024',
            issue_date=timezone.now().date() - timedelta(days=350),
            expiry_date=timezone.now().date() + timedelta(days=15),
            is_verified=True
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
        
        response = self.client.post(login_url, {
            'email': 'hr@test.com',
            'password': 'HrPass123!'
        })
        self.hr_token = response.data['access']
    
    def test_dashboard_stats_as_admin(self):
        """Test dashboard statistics for admin."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('dashboard-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('license_status', response.data)
        self.assertIn('verification_stats', response.data)
        self.assertIn('expiring_soon_breakdown', response.data)
        
        # Check summary statistics
        summary = response.data['summary']
        self.assertGreaterEqual(summary['total_agents'], 3)
        self.assertGreaterEqual(summary['total_licenses'], 3)
        
        # Check license statuses
        license_status = response.data['license_status']
        self.assertGreaterEqual(license_status['compliant'], 1)
        self.assertGreaterEqual(license_status['expired'], 1)
        self.assertGreaterEqual(license_status['expiring_soon'], 1)
    
    def test_dashboard_stats_as_hr(self):
        """Test dashboard statistics for HR."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.hr_token}')
        url = reverse('dashboard-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
    
    def test_dashboard_stats_as_agent(self):
        """Test agent cannot access admin dashboard."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('dashboard-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_agent_dashboard(self):
        """Test agent personal dashboard."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('agent-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['has_license'])
        self.assertIn('license_info', response.data)
        self.assertEqual(response.data['license_info']['license_number'], 'IRA-12345-2024')
    
    def test_agent_dashboard_without_license(self):
        """Test agent dashboard when agent has no license."""
        new_agent = User.objects.create_user(
            email='newagent@test.com',
            password='TestPass123!',
            first_name='New',
            last_name='Agent',
            role='agent'
        )
        
        login_url = reverse('token_obtain_pair')
        response = self.client.post(login_url, {
            'email': 'newagent@test.com',
            'password': 'TestPass123!'
        })
        token = response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('agent-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['has_license'])
    
    def test_compliance_report(self):
        """Test compliance report generation."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('compliance-report')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('generated_at', response.data)
        self.assertIn('overall_compliance', response.data)
        self.assertIn('expired_licenses', response.data)
        self.assertIn('expiring_soon', response.data)
        self.assertIn('agents_without_licenses', response.data)
        
        # Check expired licenses
        self.assertGreaterEqual(len(response.data['expired_licenses']), 1)
        
        # Check expiring soon
        self.assertGreaterEqual(len(response.data['expiring_soon']), 1)
    
    def test_compliance_report_as_agent(self):
        """Test agent cannot access compliance report."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('compliance-report')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_dashboard_stats_cache(self):
        """Test dashboard statistics are cached."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('dashboard-stats')
        
        # First request
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Second request should be cached
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        
        # Data should be the same
        self.assertEqual(
            response1.data['summary']['total_agents'],
            response2.data['summary']['total_agents']
        )