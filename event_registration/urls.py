from django.urls import path
from .views import SendOTP, VerifyOTP, LatestActiveEventView, CreateProfileAndBookingView

urlpatterns = [
    path('send-otp', SendOTP.as_view(), name='send-otp'),
    path('verify-otp', VerifyOTP.as_view(), name='verify-otp'),
    path('latest-event-details', LatestActiveEventView.as_view(), name='latest-event-details'),
    path('book-tickets', CreateProfileAndBookingView.as_view(), name='book-tickets'),
]