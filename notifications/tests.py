from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import Notification, EmailLog
from licenses.models import License

User = get_user_model()


class NotificationModelTests(TestCase):
    """Test cases for Notification model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='agent@test.com',
            password='TestPass123!',
            first_name='Test',
            last_name='Agent',
            role='agent'
        )
        
        self.notification = Notification.objects.create(
            user=self.user,
            type='license_expiry',
            priority='high',
            title='Test Notification',
            message='This is a test notification',
            metadata={'test': True}
        )
    
    def test_notification_creation(self):
        """Test notification creation."""
        self.assertEqual(self.notification.user, self.user)
        self.assertEqual(self.notification.type, 'license_expiry')
        self.assertFalse(self.notification.is_read)
    
    def test_mark_as_read(self):
        """Test marking notification as read."""
        self.assertFalse(self.notification.is_read)
        self.assertIsNone(self.notification.read_at)
        
        self.notification.mark_as_read()
        
        self.assertTrue(self.notification.is_read)
        self.assertIsNotNone(self.notification.read_at)
    
    def test_notification_str_method(self):
        """Test notification string representation."""
        expected = f"{self.notification.get_type_display()} - {self.user.email}"
        self.assertEqual(str(self.notification), expected)
    
    def test_notification_priority_choices(self):
        """Test notification priority choices."""
        notification = Notification.objects.create(
            user=self.user,
            type='status_change',
            priority='urgent',
            title='Urgent',
            message='Urgent message'
        )
        self.assertEqual(notification.priority, 'urgent')


class EmailLogModelTests(TestCase):
    """Test cases for EmailLog model."""
    
    def setUp(self):
        self.email_log = EmailLog.objects.create(
            recipient='test@example.com',
            subject='Test Email',
            template_name='welcome_email',
            status='pending',
            metadata={'test': True}
        )
    
    def test_email_log_creation(self):
        """Test email log creation."""
        self.assertEqual(self.email_log.recipient, 'test@example.com')
        self.assertEqual(self.email_log.status, 'pending')
    
    def test_email_log_status_choices(self):
        """Test email log status choices."""
        log = EmailLog.objects.create(
            recipient='test2@example.com',
            subject='Test',
            template_name='test',
            status='sent',
            sent_at=timezone.now()
        )
        self.assertEqual(log.status, 'sent')
        self.assertIsNotNone(log.sent_at)
    
    def test_email_log_str_method(self):
        """Test email log string representation."""
        expected = f"Email to {self.email_log.recipient} - {self.email_log.subject}"
        self.assertEqual(str(self.email_log), expected)


class NotificationAPITests(APITestCase):
    """Test cases for Notification API endpoints."""
    
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
        
        # Create notifications
        Notification.objects.create(
            user=self.agent,
            type='license_expiry',
            priority='high',
            title='License Expiring',
            message='Your license is expiring soon'
        )
        
        Notification.objects.create(
            user=self.agent,
            type='license_verified',
            priority='medium',
            title='License Verified',
            message='Your license has been verified',
            is_read=True,
            read_at=timezone.now()
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
    
    def test_list_notifications(self):
        """Test listing notifications."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('notification-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('unread_count', response.data)
        self.assertEqual(response.data['unread_count'], 1)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_filter_unread_notifications(self):
        """Test filtering unread notifications."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('notification-list')
        
        response = self.client.get(f'{url}?is_read=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for notification in response.data['results']:
            self.assertFalse(notification['is_read'])
    
    def test_mark_all_read(self):
        """Test marking all notifications as read."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('notification-mark-all-read')
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['updated_count'], 0)
        
        # Verify all are read
        unread_count = Notification.objects.filter(
            user=self.agent,
            is_read=False
        ).count()
        self.assertEqual(unread_count, 0)
    
    def test_mark_single_read(self):
        """Test marking a single notification as read."""
        notification = Notification.objects.filter(
            user=self.agent,
            is_read=False
        ).first()
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('notification-mark-read', kwargs={'pk': notification.id})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify it's read
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
    
    def test_unread_count(self):
        """Test getting unread count."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('notification-unread-count')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 1)
    
    def test_agent_cannot_see_others_notifications(self):
        """Test agent cannot see other users' notifications."""
        # Create notification for admin
        Notification.objects.create(
            user=self.admin,
            type='account_created',
            priority='low',
            title='Welcome',
            message='Welcome admin'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('notification-list')
        response = self.client.get(url)
        
        # Agent should only see their own notifications
        for notification in response.data['results']:
            self.assertNotEqual(notification['title'], 'Welcome')