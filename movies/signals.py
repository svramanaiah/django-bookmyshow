# movies/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking
from django.core.mail import send_mail
from django.conf import settings


@receiver(post_save, sender=Booking)
def update_seat_availability(sender, instance, created, **kwargs):
    if created:
        seat = instance.seat
        seat.is_booked = True
        seat.save()


# @receiver(post_save, sender=Booking)
# def update_seat_availability_and_send_email(sender, instance, created, **kwargs):
#     if created:
#         # ✅ Mark seat as booked
#         seat = instance.seat
#         seat.is_booked = True
#         seat.save()

#         # ✅ Send confirmation email
#         user_email = instance.user.email
#         subject = '🎟️ Ticket Booking Confirmation'
#         message = f'''
# Hi {instance.user.username},

# Your booking was successful!

# Movie: {instance.movie.name}
# Theater: {instance.theater.name}
# Show Time: {instance.theater.time.strftime('%A, %d %B %Y, %I:%M %p')}
# Seat Number: {seat.seat_number}

# Please arrive 15 minutes before the show.

# Thank you for booking with BookMySeat!
# '''
#         send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])
