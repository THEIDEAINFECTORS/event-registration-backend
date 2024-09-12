from django.contrib import admin
from .models import OTP, Profile, Event, EventBooking, Ticket, User

admin.site.register(OTP)
admin.site.register(Profile)
admin.site.register(Event)
admin.site.register(EventBooking)
admin.site.register(Ticket)
admin.site.register(User)
