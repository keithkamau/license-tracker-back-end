from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from licenses.models import License
import random


class Command(BaseCommand):
    help = 'Create dummy data for testing'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Creating dummy data...')
        
        # Create admin user
        admin, created = User.objects.get_or_create(
            email='admin@example.com',
            defaults={
                'first_name': 'Admin',
                'last_name': 'User',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'employee_id': 'ADM001'
            }
        )
        if created:
            admin.set_password('Admin123!')
            admin.save()
            self.stdout.write(self.style.SUCCESS('Created admin user'))
        
        # Create HR user
        hr, created = User.objects.get_or_create(
            email='hr@example.com',
            defaults={
                'first_name': 'HR',
                'last_name': 'Manager',
                'role': 'hr',
                'employee_id': 'HR001'
            }
        )
        if created:
            hr.set_password('Hr123!')
            hr.save()
            self.stdout.write(self.style.SUCCESS('Created HR user'))
        
        # Create sample agents
        agents_data = [
            {'first_name': 'John', 'last_name': 'Kamau', 'email': 'john@example.com'},
            {'first_name': 'Jane', 'last_name': 'Wanjiku', 'email': 'jane@example.com'},
            {'first_name': 'Peter', 'last_name': 'Otieno', 'email': 'peter@example.com'},
            {'first_name': 'Mary', 'last_name': 'Akinyi', 'email': 'mary@example.com'},
            {'first_name': 'David', 'last_name': 'Muthoka', 'email': 'david@example.com'},
        ]
        
        agents = []
        for i, data in enumerate(agents_data, 1):
            agent, created = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'role': 'agent',
                    'employee_id': f'AGT{i:03d}',
                    'phone_number': f'+254700{random.randint(100000, 999999)}'
                }
            )
            if created:
                agent.set_password('Agent123!')
                agent.save()
                agents.append(agent)
                self.stdout.write(self.style.SUCCESS(f'Created agent: {agent.email}'))
        
        # Create licenses with different statuses
        now = timezone.now().date()
        
        license_statuses = [
            # (agent_index, expiry_offset_days, status_scenario)
            (0, 365, 'compliant'),      # Compliant - far future
            (1, 60, 'compliant'),       # Compliant - comfortable
            (2, 20, 'expiring_soon'),   # Expiring soon - 20 days
            (3, 5, 'expiring_soon'),    # Expiring soon - 5 days
            (4, -10, 'expired'),        # Expired - 10 days ago
        ]
        
        for agent_idx, offset, scenario in license_statuses:
            expiry_date = now + timedelta(days=offset)
            issue_date = expiry_date - timedelta(days=365)
            
            License.objects.get_or_create(
                agent=agents[agent_idx],
                defaults={
                    'license_number': f'IRA-{random.randint(10000, 99999)}-{now.year}',
                    'issue_date': issue_date,
                    'expiry_date': expiry_date,
                    'is_verified': True if scenario == 'compliant' else False
                }
            )
        
        self.stdout.write(self.style.SUCCESS('Successfully created all dummy data'))