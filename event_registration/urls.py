from django.urls import path
from .views import (SendOTP, VerifyOTP, LatestActiveEventView, CreateProfileAndBookingView, 
                    CallbackForPaymentGateway, CheckPaymentStatus, RefreshTokenView, VerifyTokenView, 
                    LogoutView, UserEventBookingsView)

urlpatterns = [
    path('send-otp', SendOTP.as_view(), name='send-otp'),
    path('verify-otp', VerifyOTP.as_view(), name='verify-otp'),
    path('latest-event-details', LatestActiveEventView.as_view(), name='latest-event-details'),
    path('book-tickets', CreateProfileAndBookingView.as_view(), name='book-tickets'),
    path('callback-for-razorpay', CallbackForPaymentGateway.as_view(), name='callback-for-razorpay'),
    path('check-payment-status', CheckPaymentStatus.as_view(), name='check-payment-status'),
    path('verify-token', VerifyTokenView.as_view(), name='verify-token'),
    path('refresh-token', RefreshTokenView.as_view(), name='refresh-token'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('user-event-booking', UserEventBookingsView.as_view(), name='user-event-booking'),
]