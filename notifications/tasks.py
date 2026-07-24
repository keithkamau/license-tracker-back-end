from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

from licenses.models import License
from accounts.models import User
from .models import Notification, EmailLog

logger = logging.getLogger(__name__)


@shared_task
def send_license_expiry_reminders():
    """
    Daily task to send license expiry reminders.
    Sends emails at 30, 15, and 7 days before expiry.
    """
    today = timezone.now().date()
    logger.info(f"Starting license expiry reminders for {today}")
    
    reminder_periods = [
        (30, 'reminder_30_sent'),
        (15, 'reminder_15_sent'),
        (7, 'reminder_7_sent'),
    ]
    
    reminders_sent = 0
    
    for days_before, reminder_field in reminder_periods:
        target_date = today + timedelta(days=days_before)
        
        licenses = License.objects.filter(
            expiry_date=target_date,
            is_verified=True,
            **{reminder_field: False}
        ).select_related('agent')
        
        for license in licenses:
            try:
                context = {
                    'agent_name': license.agent.get_full_name(),
                    'license_number': license.license_number,
                    'expiry_date': license.expiry_date,
                    'days_remaining': days_before,
                    'renewal_url': f"{settings.FRONTEND_URL}/renew-license",
                    'company_name': 'Your Insurance Brokerage',
                    'current_year': today.year,
                }
                
                html_message = render_to_string('emails/license_expiry_reminder.html', context)
                plain_message = render_to_string('emails/license_expiry_reminder.txt', context)
                
                send_mail(
                    subject=f'License Expiry Reminder - {days_before} Days Remaining',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[license.agent.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                EmailLog.objects.create(
                    recipient=license.agent.email,
                    subject=f'License Expiry Reminder - {days_before} Days',
                    template_name='license_expiry_reminder',
                    status=EmailLog.Status.SENT,
                    sent_at=timezone.now(),
                    metadata={
                        'license_id': str(license.id),
                        'days_before': days_before,
                        'agent_id': str(license.agent.id)
                    }
                )
                
                Notification.objects.create(
                    user=license.agent,
                    type=Notification.Type.LICENSE_EXPIRY,
                    priority=Notification.Priority.HIGH if days_before <= 7 else Notification.Priority.MEDIUM,
                    title=f'License Expiring in {days_before} Days',
                    message=f'Your IRA license ({license.license_number}) will expire on {license.expiry_date}. Please renew.',
                    metadata={
                        'license_id': str(license.id),
                        'expiry_date': str(license.expiry_date),
                        'days_remaining': days_before
                    }
                )
                
                if days_before <= 7:
                    send_mail(
                        subject=f'URGENT: Agent License Expiring - {license.agent.get_full_name()}',
                        message=f'Agent {license.agent.get_full_name()} license will expire in {days_before} days.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.ADMIN_EMAIL],
                        fail_silently=False,
                    )
                    
                    hr_users = User.objects.filter(role='hr', is_active=True)
                    for hr in hr_users:
                        Notification.objects.create(
                            user=hr,
                            type=Notification.Type.LICENSE_EXPIRY,
                            priority=Notification.Priority.URGENT,
                            title=f'URGENT: Agent License Expiring',
                            message=f'{license.agent.get_full_name()} license expires in {days_before} days.',
                            metadata={
                                'license_id': str(license.id),
                                'agent_id': str(license.agent.id),
                                'days_remaining': days_before
                            }
                        )
                
                setattr(license, reminder_field, True)
                license.save(update_fields=[reminder_field])
                
                reminders_sent += 1
                logger.info(f"Sent {days_before}-day reminder to {license.agent.email}")
                
            except Exception as e:
                logger.error(f"Failed to send reminder to {license.agent.email}: {str(e)}")
                
                EmailLog.objects.create(
                    recipient=license.agent.email,
                    subject=f'License Expiry Reminder - {days_before} Days',
                    template_name='license_expiry_reminder',
                    status=EmailLog.Status.FAILED,
                    error_message=str(e),
                    metadata={'license_id': str(license.id)}
                )
    
    logger.info(f"Completed sending {reminders_sent} reminders")
    return f"Sent {reminders_sent} reminders"


@shared_task
def send_welcome_email(user_id):
    """Send welcome email to new users."""
    try:
        user = User.objects.get(id=user_id)
        
        context = {
            'user_name': user.get_full_name(),
            'role': user.get_role_display(),
            'login_url': f"{settings.FRONTEND_URL}/login",
            'company_name': 'Your Insurance Brokerage',
            'current_year': timezone.now().year,
        }
        
        html_message = render_to_string('emails/welcome_email.html', context)
        plain_message = f"""
Welcome {user.get_full_name()}!

Your account has been created as {user.get_role_display()}.
You can log in at: {settings.FRONTEND_URL}/login

If you have any questions, please contact HR.
        """
        
        send_mail(
            subject='Welcome to License Compliance Tracker',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        Notification.objects.create(
            user=user,
            type=Notification.Type.ACCOUNT_CREATED,
            priority=Notification.Priority.LOW,
            title='Welcome to License Compliance Tracker',
            message=f'Your account has been created. Please log in and upload your license if you are an agent.',
        )
        
        EmailLog.objects.create(
            recipient=user.email,
            subject='Welcome to License Compliance Tracker',
            template_name='welcome_email',
            status=EmailLog.Status.SENT,
            sent_at=timezone.now(),
            metadata={'user_id': str(user.id)}
        )
        
        return f"Welcome email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return f"User {user_id} not found"
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return f"Failed to send welcome email: {str(e)}"


@shared_task
def notify_license_status_change(license_id, status, verified_by_id=None):
    """Notify agent when their license status changes."""
    try:
        license = License.objects.select_related('agent').get(id=license_id)
        
        messages = {
            'compliant': 'Your license has been verified and is compliant.',
            'expiring_soon': 'Your license is expiring soon. Please prepare for renewal.',
            'expired': 'Your license has expired. Please renew immediately.',
            'pending': 'Your license is pending verification.',
        }
        
        message = messages.get(status, f'Your license status has been updated to {status}.')
        
        Notification.objects.create(
            user=license.agent,
            type=Notification.Type.STATUS_CHANGE if status != 'compliant' else Notification.Type.LICENSE_VERIFIED,
            priority=Notification.Priority.URGENT if status == 'expired' else Notification.Priority.MEDIUM,
            title=f'License Status: {license.get_status_display()}',
            message=message,
            metadata={
                'license_id': str(license.id),
                'status': status,
                'verified_by': str(verified_by_id) if verified_by_id else None
            }
        )
        
        return f"Status notification sent to {license.agent.email}"
        
    except License.DoesNotExist:
        logger.error(f"License {license_id} not found")
        return f"License {license_id} not found"
    except Exception as e:
        logger.error(f"Failed to send status notification: {str(e)}")
        return f"Failed to send status notification: {str(e)}"


@shared_task
def cleanup_old_notifications():
    """Clean up notifications older than 90 days."""
    from datetime import timedelta
    cutoff_date = timezone.now() - timedelta(days=90)
    
    deleted_count = Notification.objects.filter(
        created_at__lt=cutoff_date,
        is_read=True
    ).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old notifications")
    return f"Cleaned up {deleted_count} old notifications"


@shared_task
def send_daily_digest():
    """Send daily digest to admins and HR about license statuses."""
    today = timezone.now().date()
    
    total_licenses = License.objects.count()
    expired_count = License.objects.filter(status='expired').count()
    expiring_soon_count = License.objects.filter(status='expiring_soon').count()
    pending_count = License.objects.filter(status='pending').count()
    
    context = {
        'date': today,
        'total_licenses': total_licenses,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'pending_count': pending_count,
        'compliant_count': total_licenses - expired_count - expiring_soon_count - pending_count,
        'dashboard_url': f"{settings.FRONTEND_URL}/dashboard",
    }
    
    admin_users = User.objects.filter(
        role__in=['admin', 'hr'],
        is_active=True
    )
    
    for admin in admin_users:
        try:
            send_mail(
                subject=f'Daily License Status Digest - {today}',
                message=f"""
Daily License Status Digest

Date: {today}
Total Licenses: {total_licenses}
Compliant: {context['compliant_count']}
Expiring Soon: {expiring_soon_count}
Expired: {expired_count}
Pending: {pending_count}

View dashboard: {settings.FRONTEND_URL}/dashboard
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send digest to {admin.email}: {str(e)}")
    
    return f"Daily digest sent to {admin_users.count()} admins"