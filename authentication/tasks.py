"""
Celery Tasks for Authentication App
====================================

This module contains asynchronous tasks that run in the background
using Celery task queue.

Usage:
    # Import and call a task
    from authentication.tasks import send_welcome_email
    send_welcome_email.delay(user_id=1)
    
    # Or with apply_async for more options
    send_welcome_email.apply_async(
        args=[user_id],
        countdown=60  # Execute after 60 seconds
    )
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# ====================
# Email Tasks
# ====================

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    """
    Send welcome email to a new user.
    
    Args:
        user_id (int): The ID of the user
        
    Usage:
        send_welcome_email.delay(user_id=1)
    """
    from authentication.models import User
    from django.template.loader import render_to_string
    from datetime import datetime
    
    try:
        user = User.objects.get(id=user_id)
        
        subject = 'Welcome to 1Source.Chat'
        
        # Plain text message
        message = f'''
Hello {user.email},

Welcome to Pi! We're excited to have you on board.

Your role: {user.role_name if user.role else 'Not assigned'}

Get started by:
1. Setting up your profile
2. Joining channels
3. Connecting with team members

Best regards,
1Source.Chat
        '''
        
        # Render HTML template
        html_message = render_to_string('authentication/emails/welcome_email.html', {
            'user': user,
            'current_year': datetime.now().year,
        })
        
        send_mail(
            subject=subject,
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return f"Email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist")
        raise
    except Exception as exc:
        logger.error(f"Error sending welcome email: {exc}")
        # Retry the task
        raise self.retry(exc=exc, countdown=60)


@shared_task
def send_password_reset_email(user_id, reset_token):
    """
    Send password reset email.
    
    Args:
        user_id (int): User ID
        reset_token (str): Password reset token
        
    Usage:
        send_password_reset_email.delay(user_id=1, reset_token='abc123')
    """
    from authentication.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        subject = 'Password Reset Request'
        message = f'''
        Hello {user.email},
        
        You requested to reset your password.
        
        Use this token to reset your password: {reset_token}
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        1Source.Chat
        '''
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        
        logger.info(f"Password reset email sent to {user.email}")
        return f"Password reset email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist")


@shared_task(bind=True, max_retries=3)
def send_otp_email(self, user_id, otp):
    """
    Send OTP (One-Time Password) email to user.
    
    Args:
        user_id (int): User ID
        otp (str): 6-digit OTP code
        
    Usage:
        send_otp_email.delay(user_id=1, otp='123456')
    """
    from authentication.models import User
    from django.template.loader import render_to_string
    from datetime import datetime
    
    logger.info(f"[OTP] Starting OTP email task for user_id={user_id}")
    
    try:
        user = User.objects.get(id=user_id)
        
        logger.info(f"[OTP] Sending OTP {otp} to {user.email}")
        
        subject = 'Your OTP Code - 1Source.Chat'
        
        # Plain text message
        message = f'''
                        Hello {user.email},

                        Your One-Time Password (OTP) is: {otp}

                        This OTP is valid for 10 minutes.

                        If you didn't request this code, please ignore this email.

                        Best regards,
                        1Source.Chat
                    '''
        
        # Render HTML template
        html_message = render_to_string('authentication/emails/otp_email.html', {
            'user': user,
            'otp': otp,
            'current_year': datetime.now().year,
        })
        
        send_mail(
            subject=subject,
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"[OTP] ✓ OTP email sent successfully to {user.email}")
        return f"OTP sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"[OTP] ✗ User with id {user_id} does not exist")
        raise
    except Exception as exc:
        logger.error(f"[OTP] ✗ Error sending OTP email: {exc}")
        # Retry the task
        raise self.retry(exc=exc, countdown=30)


# ====================
# Notification Tasks
# ====================

@shared_task
def send_notification(user_id, notification_type, message):
    """
    Send notification to a user.
    
    Args:
        user_id (int): User ID
        notification_type (str): Type of notification
        message (str): Notification message
        
    Usage:
        send_notification.delay(
            user_id=1,
            notification_type='message',
            message='You have a new message'
        )
    """
    from authentication.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        # Here you would implement your notification logic
        # Could be:
        # - WebSocket notification
        # - Push notification
        # - Email notification
        # - SMS notification
        
        logger.info(f"Notification sent to {user.email}: {notification_type} - {message}")
        return f"Notification sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist")


@shared_task
def send_bulk_notification(user_ids, message):
    """
    Send notification to multiple users.
    
    Args:
        user_ids (list): List of user IDs
        message (str): Notification message
        
    Usage:
        send_bulk_notification.delay(
            user_ids=[1, 2, 3],
            message='System maintenance in 1 hour'
        )
    """
    from authentication.models import User
    
    users = User.objects.filter(id__in=user_ids)
    count = 0
    
    for user in users:
        # Send notification to each user
        send_notification.delay(user.id, 'system', message)
        count += 1
    
    logger.info(f"Bulk notification sent to {count} users")
    return f"Notification sent to {count} users"


# ====================
# Data Processing Tasks
# ====================

@shared_task
def cleanup_old_data():
    """
    Periodic task to clean up old data.
    This can be scheduled using Celery Beat.
    
    Usage (in celery.py beat_schedule):
        'cleanup-old-data': {
            'task': 'authentication.tasks.cleanup_old_data',
            'schedule': crontab(hour=0, minute=0),  # Daily at midnight
        },
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Example: Delete inactive users older than 1 year
    cutoff_date = timezone.now() - timedelta(days=365)
    
    # Implement your cleanup logic here
    # deleted_count = OldModel.objects.filter(
    #     created_at__lt=cutoff_date,
    #     is_active=False
    # ).delete()
    
    logger.info(f"Cleanup task completed")
    return "Cleanup completed"


@shared_task
def generate_user_report(user_id):
    """
    Generate a comprehensive report for a user.
    
    Args:
        user_id (int): User ID
        
    Usage:
        task = generate_user_report.delay(user_id=1)
        # Check result later
        result = task.get()
    """
    from authentication.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        report = {
            'user': user.email,
            'role': user.role_name,
            'status': user.status,
            'permissions': list(user.get_all_permissions().values_list('codename', flat=True)),
            'generated_at': timezone.now().isoformat(),
        }
        
        logger.info(f"Report generated for {user.email}")
        return report
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist")
        return None


# ====================
# Role & Permission Tasks
# ====================

@shared_task
def update_user_roles(role_slug, user_ids):
    """
    Bulk update user roles.
    
    Args:
        role_slug (str): Role slug to assign
        user_ids (list): List of user IDs
        
    Usage:
        update_user_roles.delay(
            role_slug='team_member',
            user_ids=[1, 2, 3, 4, 5]
        )
    """
    from authentication.models import User, Role
    
    try:
        role = Role.objects.get(slug=role_slug)
        updated_count = User.objects.filter(id__in=user_ids).update(role=role)
        
        logger.info(f"Updated {updated_count} users to role: {role.name}")
        return f"Updated {updated_count} users"
        
    except Role.DoesNotExist:
        logger.error(f"Role with slug {role_slug} does not exist")
        return "Role not found"


@shared_task
def sync_permissions():
    """
    Sync permissions from code to database.
    Useful for keeping permissions up to date in production.
    
    Usage:
        sync_permissions.delay()
    """
    from django.core.management import call_command
    
    try:
        # Run the seed_permissions command
        call_command('seed_permissions')
        
        logger.info("Permissions synced successfully")
        return "Permissions synced"
        
    except Exception as e:
        logger.error(f"Error syncing permissions: {e}")
        return f"Error: {str(e)}"



