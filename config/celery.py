import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('license_tracker')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'send-license-reminders-daily': {
        'task': 'notifications.tasks.send_license_expiry_reminders',
        'schedule': crontab(hour=8, minute=0),  # Every day at 8:00 AM
    },
    'cleanup-old-notifications': {
        'task': 'notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=0, minute=0, day_of_week=1),  # Every Monday at midnight
    },
    'send-daily-digest': {
        'task': 'notifications.tasks.send_daily_digest',
        'schedule': crontab(hour=9, minute=0),  # Every day at 9:00 AM
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')