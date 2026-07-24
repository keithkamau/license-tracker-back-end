from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse

User = get_user_model()


class UserModelTests(TestCase):
    """Test cases for User model."""
    
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'TestPass123!',
            'role': 'agent'
        }
    
    def test_create_user(self):
        """Test creating a regular user."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.role, 'agent')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
    
    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User'
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, 'admin')
    
    def test_user_str_method(self):
        """Test user string representation."""
        user = User.objects.create_user(**self.user_data)
        expected_str = f"{user.get_full_name()} ({user.email})"
        self.assertEqual(str(user), expected_str)
    
    def test_get_full_name(self):
        """Test getting full name."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.get_full_name(), 'Test User')
    
    def test_create_user_without_email(self):
        """Test creating user without email raises error."""
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='TestPass123!')
    
    def test_user_roles(self):
        """Test role properties."""
        admin = User.objects.create_user(
            email='admin@test.com',
            password='TestPass123!',
            role='admin'
        )
        hr = User.objects.create_user(
            email='hr@test.com',
            password='TestPass123!',
            role='hr'
        )
        agent = User.objects.create_user(**self.user_data)
        
        self.assertTrue(admin.is_admin)
        self.assertTrue(hr.is_hr)
        self.assertTrue(agent.is_agent)
    
    def test_unique_email(self):
        """Test email uniqueness."""
        User.objects.create_user(**self.user_data)
        with self.assertRaises(Exception):
            User.objects.create_user(
                email='test@example.com',
                password='TestPass123!'
            )
    
    def test_phone_number_validation(self):
        """Test phone number format validation."""
        user = User.objects.create_user(**self.user_data)
        
        # Valid phone number
        user.phone_number = '+254712345678'
        user.full_clean()
        
        # Invalid phone number
        user.phone_number = '12345'
        with self.assertRaises(Exception):
            user.full_clean()


class UserAPITests(APITestCase):
    """Test cases for User API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create test users
        self.admin = User.objects.create_superuser(
            email='admin@test.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User'
        )
        
        self.agent = User.objects.create_user(
            email='agent@test.com',
            password='AgentPass123!',
            first_name='Agent',
            last_name='User',
            role='agent'
        )
        
        self.hr = User.objects.create_user(
            email='hr@test.com',
            password='HrPass123!',
            first_name='HR',
            last_name='User',
            role='hr'
        )
        
        # Get JWT tokens
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
    
    def test_user_login(self):
        """Test user login endpoint."""
        url = reverse('token_obtain_pair')
        
        # Valid login
        response = self.client.post(url, {
            'email': 'agent@test.com',
            'password': 'AgentPass123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        
        # Invalid login
        response = self.client.post(url, {
            'email': 'agent@test.com',
            'password': 'WrongPass123!'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_refresh(self):
        """Test token refresh endpoint."""
        login_url = reverse('token_obtain_pair')
        response = self.client.post(login_url, {
            'email': 'agent@test.com',
            'password': 'AgentPass123!'
        })
        refresh_token = response.data['refresh']
        
        refresh_url = reverse('token_refresh')
        response = self.client.post(refresh_url, {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_list_users_as_admin(self):
        """Test listing users as admin."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('user-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 3)
    
    def test_list_users_as_agent(self):
        """Test agents cannot list users."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('user-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Agent should only see themselves
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_user_as_admin(self):
        """Test creating user as admin."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('user-list')
        
        data = {
            'email': 'newagent@test.com',
            'first_name': 'New',
            'last_name': 'Agent',
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
            'role': 'agent'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'newagent@test.com')
    
    def test_create_user_as_agent(self):
        """Test agents cannot create users."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('user-list')
        
        data = {
            'email': 'newagent@test.com',
            'first_name': 'New',
            'last_name': 'Agent',
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
            'role': 'agent'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_me(self):
        """Test getting current user profile."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('user-me')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'agent@test.com')
    
    def test_change_password(self):
        """Test changing password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.agent_token}')
        url = reverse('user-change-password')
        
        data = {
            'old_password': 'AgentPass123!',
            'new_password': 'NewAgentPass123!',
            'confirm_password': 'NewAgentPass123!'
        }
        
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Try logging in with new password
        login_url = reverse('token_obtain_pair')
        response = self.client.post(login_url, {
            'email': 'agent@test.com',
            'password': 'NewAgentPass123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_toggle_user_status(self):
        """Test toggling user active status."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('user-toggle-status', kwargs={'pk': self.agent.id})
        
        response = self.client.put(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])
        
        # Toggle back
        response = self.client.put(url)
        self.assertTrue(response.data['is_active'])
    
    def test_filter_users_by_role(self):
        """Test filtering users by role."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('user-list')
        
        response = self.client.get(f'{url}?role=agent')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for user in response.data['results']:
            self.assertEqual(user['role'], 'agent')
    
    def test_search_users(self):
        """Test searching users."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = reverse('user-list')
        
        response = self.client.get(f'{url}?search=admin')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)