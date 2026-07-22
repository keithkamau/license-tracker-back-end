from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from .models import License, LicenseAudit

User = get_user_model()


class LicenseModelTests(TestCase):
    """Test cases for License model."""
    
    def setUp(self):
        self.agent = User.objects.create_user(
            email='agent@test.com',
            password='TestPass123!',
            first_name='Test',
            last_name='Agent',
            role='agent'
        )
        
        self.license = License.objects.create(
            agent=self.agent,
            license_number='IRA-12345-2024',
            issue_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timedelta(days=365),
            is_verified=True
        )
    
    def test_license_creation(self):
        """Test license creation."""
        self.assertEqual(self.license.agent, self.agent)
        self.assertEqual(self.license.status, 'compliant')
        self.assertTrue(self.license.is_verified)
    
    def test_license_status_compliant(self):
        """Test compliant status calculation."""
        self.assertEqual(self.license.status, 'compliant')
        self.assertEqual(self.license.days_until_expiry, 365)
    
    def test_license_status_expiring_soon(self):
        """Test expiring soon status calculation."""
        self.license.expiry_date = timezone.now().date() + timedelta(days=20)
        self.license.save()
        self.assertEqual(self.license.status, 'expiring_soon')
    
    def test_license_status_expired(self):
        """Test expired status calculation."""
        self.license.expiry_date = timezone.now().date() - timedelta(days=10)
        self.license.save()
        self.assertEqual(self.license.status, 'expired')
    
    def test_license_unique_agent(self):
        """Test one license per agent."""
        with self.assertRaises(Exception):
            License.objects.create(
                agent=self.agent,
                license_number='IRA-99999-2024',
                issue_date=timezone.now().date(),
                expiry_date=timezone.now().date() + timedelta(days=365)
            )
    
    def test_license_unique_number(self):
        """Test unique license number."""
        new_agent = User.objects.create_user(
            email='agent2@test.com',
            password='TestPass123!',
            first_name='Test',
            last_name='Agent2',
            role='agent'
        )
        
        with self.assertRaises(Exception):
            License.objects.create(
                agent=new_agent,
                license_number='IRA-12345-2024',
                issue_date=timezone.now().date(),
                expiry_date=timezone.now().date() + timedelta(days=365)
            )
    
    def test_days_until_expiry(self):
        """Test days until expiry calculation."""
        days = self.license.days_until_expiry
        self.assertEqual(days, 365)
        
        self.license.expiry_date = timezone.now().date() - timedelta(days=5)
        self.license.save()
        self.assertEqual(self.license.days_until_expiry, -5)
    
    def test_license_str_method(self):
        """Test license string representation."""
        expected = f"{self.agent.get_full_name()} - {self.license.license_number}"
        self.assertEqual(str(self.license), expected)


class LicenseAPITests(APITestCase):
    """Test cases for License API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create users
        self.agent = User.objects.create_user(
            email='agent@test.com',
            password='AgentPass123!',
            first_name='Test',
            last_name='Agent',
            role='agent'
        )
        
        self.admin = User.objects.create_superuser(
            email='admin@test.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User'
        )
        
        self.hr = User.objects.create_user(
            email='hr@test.com',
            password='HrPass123!',
            first_name='HR',
            last_name='User',
            role='hr'
        )
        
        self.agent2 = User.objects.create_user(
            email='agent2@test.com',
            password='AgentPass123!',
            first_name='Test2',
            last_name='Agent',
            role='agent'
        )
        
        # Create license for agent2
        self.license = License.objects.create(
            agent=self.agent2,
            license_number='IRA-12345-2024',
            issue_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timedelta(days=365),
            is_verified=True
        )
        
        # Get tokens
        login_url = reverse('token_obtain_pair')
        
        response = self.client.post(login_url, {
            'email': 'agent@test.com',
            'password': 'AgentPass123!'
        })
        self.agent_token = response.data['access']
        
        response = self.client.post(login_url, {
            'email': 'admin@test.com',
            'password': 'AdminPass123!'
        })
        self.admin_token = response.data['access']
        
        response = self.client.post(login_url, {
            'email': 'hr@test.com',
            'password': 'HrPass123!'
        })
        self.hr_token = response.data['access']
    
    def test_list_licenses_as_admin(self):
        """Test listing licenses as admin."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('license-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('statistics', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_list_licenses_as_agent(self):
        """Test agents only see their own license."""
        # Agent without license
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('license-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
    
    def test_create_license_as_agent(self):
        """Test creating license as agent."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('license-list')
        
        data = {
            'license_number': 'IRA-99999-2024',
            'issue_date': timezone.now().date(),
            'expiry_date': timezone.now().date() + timedelta(days=365),
            'notes': 'Test license'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['agent'], str(self.agent.id))
    
    def test_create_license_with_certificate(self):
        """Test creating license with file upload."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('license-list')
        
        # Create a test file
        test_file = SimpleUploadedFile(
            "certificate.pdf",
            b"file_content",
            content_type="application/pdf"
        )
        
        data = {
            'license_number': 'IRA-88888-2024',
            'issue_date': timezone.now().date(),
            'expiry_date': timezone.now().date() + timedelta(days=365),
            'certificate_file': test_file
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['certificate_url'])
    
    def test_verify_license_as_admin(self):
        """Test verifying a license as admin."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('license-verify', kwargs={'pk': self.license.id})
        
        data = {
            'is_verified': True,
            'notes': 'Verified successfully'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_verified'])
    
    def test_verify_license_as_agent(self):
        """Test agents cannot verify licenses."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('license-verify', kwargs={'pk': self.license.id})
        
        data = {
            'is_verified': True,
            'notes': 'Trying to verify'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_filter_licenses_by_status(self):
        """Test filtering licenses by status."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('license-list')
        
        response = self.client.get(f'{url}?status=compliant')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for license in response.data['results']:
            self.assertEqual(license['status'], 'compliant')
    
    def test_license_statistics(self):
        """Test license statistics endpoint."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('license-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total', response.data)
        self.assertIn('by_status', response.data)
        self.assertIn('compliant', response.data['by_status'])
    
    def test_export_csv(self):
        """Test CSV export functionality."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('license-export-csv')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_audit_log_creation(self):
        """Test audit log is created on license creation."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('license-list')
        
        data = {
            'license_number': 'IRA-77777-2024',
            'issue_date': timezone.now().date(),
            'expiry_date': timezone.now().date() + timedelta(days=365),
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check audit log was created
        license_id = response.data['id']
        audit_exists = LicenseAudit.objects.filter(
            license_id=license_id,
            action='created'
        ).exists()
        self.assertTrue(audit_exists)
    
    def test_license_update_with_audit(self):
        """Test license update creates audit log."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        # Update license
        url = reverse('license-detail', kwargs={'pk': self.license.id})
        data = {
            'expiry_date': timezone.now().date() + timedelta(days=400),
            'notes': 'Updated expiry date'
        }
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check audit log
        audit_exists = LicenseAudit.objects.filter(
            license=self.license,
            action='updated'
        ).exists()
        self.assertTrue(audit_exists)
    
    def test_get_license_audit_logs(self):
        """Test retrieving audit logs for a license."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        # Create an audit entry first
        self.client.patch(
            reverse('license-detail', kwargs={'pk': self.license.id}),
            {'notes': 'Test update'},
            format='json'
        )
        
        url = reverse('license-audit-log', kwargs={'pk': self.license.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_invalid_certificate_file_type(self):
        """Test uploading invalid file type."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('license-list')
        
        test_file = SimpleUploadedFile(
            "test.txt",
            b"file_content",
            content_type="text/plain"
        )
        
        data = {
            'license_number': 'IRA-66666-2024',
            'issue_date': timezone.now().date(),
            'expiry_date': timezone.now().date() + timedelta(days=365),
            'certificate_file': test_file
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_expiry_date_validation(self):
        """Test expiry date is after issue date."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('license-list')
        
        data = {
            'license_number': 'IRA-55555-2024',
            'issue_date': timezone.now().date(),
            'expiry_date': timezone.now().date() - timedelta(days=365),  # Past date
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)