from django.core.management.base import BaseCommand
from django.utils import timezone
from notifications.tasks import send_license_expiry_reminders


class Command(BaseCommand):
    help = 'Send license expiry reminder emails manually'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually sending emails',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: No emails will be sent'))
        
        self.stdout.write(f'Starting reminder check at {timezone.now()}')
        
        if not dry_run:
            result = send_license_expiry_reminders.delay()
            self.stdout.write(
                self.style.SUCCESS(f'Reminder task queued: {result.id}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Dry run completed')
            )