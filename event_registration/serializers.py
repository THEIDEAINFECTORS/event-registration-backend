from rest_framework import serializers
import re
from .models import Profile, EventBooking, Event, Ticket, User

class SendOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)

    def validate_mobile(self, value):
        # Remove country code if present
        value = re.sub(r'^\+?91|^91', '', value)

        # Ensure the number is 10 digits and only contains digits
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError("Invalid mobile number. It must be a 10-digit Indian mobile number.")

        return value
    
class VerifyOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    otp = serializers.IntegerField()

    def validate_mobile(self, value):
        # Normalize the mobile number by removing any country code
        value = re.sub(r'^\+?91|^91', '', value)
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError("Invalid mobile number. It must be a 10-digit Indian mobile number.")
        return value


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['id', 'name', 'event_date', 'event_start_time', 'event_end_time', 'active']

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'name', 'price', 'total_tickets_available']

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['name', 'age', 'mobile', 'email', 'gender']

    email = serializers.EmailField(required=False, allow_null=True)

    def validate_mobile(self, value):
        """
        Ensure that the mobile number is valid. Normalize the mobile number by removing any country code
        and ensure it is a 10-digit Indian mobile number.
        """
        if isinstance(value, int):
            value = str(value)
        elif not isinstance(value, str):
            raise serializers.ValidationError("Mobile number must be a string.")

        # Normalize the mobile number by removing any country code
        value = re.sub(r'^\+?91|^91', '', value)

        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError("Invalid mobile number. It must be a 10-digit Indian mobile number.")
        
        return value

class EventBookingSerializer(serializers.ModelSerializer):
    # Make payment_link and payment_amount optional
    payment_link = serializers.URLField(required=False)
    payment_amount = serializers.FloatField(required=False)
    location = serializers.CharField(required=False)
    cab_facility_required = serializers.BooleanField(required=False)
    address = serializers.CharField(required=False)

    class Meta:
        model = EventBooking
        fields = [
            'event', 'ticket', 'ticket_quantity', 'attending_time', 'cab_facility_required', 
            'location', 'address', 'payment_completed', 'payment_completed_at', 'payment_link', 'payment_amount'
        ]

    def validate(self, data):
        """
        Ensure ticket quantity is available before saving the booking.
        """
        ticket = data.get('ticket')
        ticket_quantity = data.get('ticket_quantity')

        if ticket is not None:
            try:
                if ticket_quantity > ticket.total_tickets_available:
                    raise serializers.ValidationError(f"Only {ticket.total_tickets_available} tickets are available.")
            except Ticket.DoesNotExist:
                raise serializers.ValidationError("Ticket does not exist.")

        return data