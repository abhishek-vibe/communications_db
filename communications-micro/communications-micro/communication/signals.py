from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import Broadcast, Event, EventRSVPLog


@receiver(post_save, sender=Broadcast)
def broadcast_created(sender, instance, created, **kwargs):
    """Handle actions when a broadcast is created or updated"""
    if created and instance.is_published and instance.send_email:
        # Send email notifications if enabled
        send_broadcast_email.delay(instance.id)


@receiver(m2m_changed, sender=Broadcast.acknowledged_by.through)
def broadcast_acknowledged(sender, instance, action, pk_set, **kwargs):
    """Handle broadcast acknowledgment"""
    if action == "post_add":
        # Optional: Send acknowledgment confirmation
        pass


@receiver(m2m_changed, sender=Event.rsvp_yes.through)
def event_rsvp_yes_changed(sender, instance, action, pk_set, **kwargs):
    """Handle RSVP Yes changes"""
    if action == "post_add" and pk_set:
        for user_id in pk_set:
            try:
                user = User.objects.get(id=user_id)
                # Create RSVP log entry
                EventRSVPLog.objects.create(
                    event=instance,
                    user=user,
                    old_status=None,  # We don't track the old status in signals
                    new_status='yes'
                )
            except User.DoesNotExist:
                pass


@receiver(m2m_changed, sender=Event.rsvp_no.through)
def event_rsvp_no_changed(sender, instance, action, pk_set, **kwargs):
    """Handle RSVP No changes"""
    if action == "post_add" and pk_set:
        for user_id in pk_set:
            try:
                user = User.objects.get(id=user_id)
                EventRSVPLog.objects.create(
                    event=instance,
                    user=user,
                    old_status=None,
                    new_status='no'
                )
            except User.DoesNotExist:
                pass


@receiver(m2m_changed, sender=Event.rsvp_maybe.through)
def event_rsvp_maybe_changed(sender, instance, action, pk_set, **kwargs):
    """Handle RSVP Maybe changes"""
    if action == "post_add" and pk_set:
        for user_id in pk_set:
            try:
                user = User.objects.get(id=user_id)
                EventRSVPLog.objects.create(
                    event=instance,
                    user=user,
                    old_status=None,
                    new_status='maybe'
                )
            except User.DoesNotExist:
                pass


# Celery tasks (if using Celery for background tasks)
try:
    from celery import shared_task
    
    @shared_task
    def send_broadcast_email(broadcast_id):
        """Send email notifications for broadcasts"""
        try:
            broadcast = Broadcast.objects.get(id=broadcast_id)
            
            # Get recipients based on audience type
            recipients = []
            if broadcast.audience_type == 'all':
                recipients = User.objects.filter(is_active=True, email__isnull=False).values_list('email', flat=True)
            elif broadcast.audience_type == 'groups':
                recipients = User.objects.filter(
                    user_groups__in=broadcast.target_groups.all(),
                    email__isnull=False
                ).distinct().values_list('email', flat=True)
            elif broadcast.audience_type == 'users':
                recipients = broadcast.target_users.filter(
                    email__isnull=False
                ).values_list('email', flat=True)
            
            if recipients:
                send_mail(
                    subject=f"[Broadcast] {broadcast.title}",
                    message=broadcast.description,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=list(recipients),
                    fail_silently=True,
                )
                
        except Broadcast.DoesNotExist:
            pass
    
    @shared_task
    def send_event_reminder(event_id):
        """Send event reminders"""
        try:
            event = Event.objects.get(id=event_id)
            
            # Get users who RSVP'd yes
            recipients = event.rsvp_yes.filter(email__isnull=False).values_list('email', flat=True)
            
            if recipients:
                send_mail(
                    subject=f"[Event Reminder] {event.title}",
                    message=f"This is a reminder for the upcoming event: {event.title}\n"
                           f"Date: {event.date}\n"
                           f"Time: {event.time}\n"
                           f"Venue: {event.venue}\n\n"
                           f"{event.description}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=list(recipients),
                    fail_silently=True,
                )
                
        except Event.DoesNotExist:
            pass

except ImportError:
    # Celery not available, define dummy functions
    def send_broadcast_email(broadcast_id):
        pass
    
    def send_event_reminder(event_id):
        pass