from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db.models import ObjectDoesNotExist
from django.db import transaction
from .models import OTP, Event, Ticket, Profile, EventBooking
from .serializers import SendOTPSerializer, VerifyOTPSerializer, EventSerializer, TicketSerializer, ProfileSerializer, EventBookingSerializer
from twilio.rest import Client
from settings.config import TWILIO_PHONE_NUMBER, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, RAZORPAY_KEY, RAZORPAY_SECRET
from .utility import generate_otp
import uuid
import razorpay
import datetime
from django.shortcuts import redirect

User = get_user_model()

class SendOTP(APIView):

    def post(self, request):
        try:

            # Use the serializer to validate the input
            serializer = SendOTPSerializer(data=request.data)
            if serializer.is_valid():
                mobile_number = serializer.validated_data['mobile']
                
                # Check if user exists, else create a new user
                user, created = User.objects.get_or_create(mobile=mobile_number)

                # Generate OTP (assuming you have a method for this)
                otp = generate_otp()

                # Calculate OTP expiration time (e.g., 10 minutes from now)
                expires_at = timezone.now() + timedelta(minutes=10)

                # Save OTP in the OTP model
                OTP.objects.create(user=user, otp=otp, created_at=timezone.now(), exprires_at=expires_at, active=True)

                # Create Twilio client
                client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

                # Send OTP message
                message = client.messages.create(
                    body=f'Your Formis Hydrovibe code is {otp}',
                    from_=TWILIO_PHONE_NUMBER,
                    to=f'+91{mobile_number}',  
                )

                data = {
                    'user': {
                        'mobile': user.mobile,
                        'is_new_user': created,
                    },
                    'Message': 'OTP sent successfully'
                }

                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            # Handle any ValueErrors that could occur (e.g., invalid data in query params)
            print(f"Value error: {e}")
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Log any unexpected exceptions and return a generic error response
            print(f"An unexpected error occurred: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class VerifyOTP(APIView):

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            mobile_number = serializer.validated_data['mobile']
            otp_input = serializer.validated_data['otp']

            try:
                # Find the user with the given mobile number
                user = User.objects.get(mobile=mobile_number)
                
                # Find the active OTP for the user
                otp_record = OTP.objects.filter(user=user, active=True).latest('created_at')
                
                # Check if OTP matches and hasn't expired
                if otp_record.otp == otp_input:
                    if otp_record.exprires_at >= timezone.now():
                        # OTP is valid, deactivate the OTP and proceed with user verification
                        otp_record.active = False
                        otp_record.save()
                        
                        return Response({"message": "OTP verified successfully!"}, status=status.HTTP_200_OK)
                    else:
                        return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)
            
            except User.DoesNotExist:
                return Response({"error": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)
            except OTP.DoesNotExist:
                return Response({"error": "No active OTP found for this user."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LatestActiveEventView(APIView):

    def get(self, request):
        try:
            # Fetch the latest active event
            event = Event.objects.filter(active=True, event_date__gte=timezone.now().date()).order_by('event_date').first()

            if not event:
                # No active event found
                raise Event.DoesNotExist("No active event available")

            # Serialize event details
            event_data = EventSerializer(event).data

            # Fetch tickets for the event
            tickets = Ticket.objects.filter(event=event).distinct()

            if not tickets.exists():
                # If no tickets are found for the event
                raise Ticket.DoesNotExist("No tickets available for this event")

            # Check if all tickets have zero availability
            total_available_tickets = sum(ticket.total_tickets_available for ticket in tickets)

            if total_available_tickets == 0:
                raise Ticket.DoesNotExist("No tickets available for this event")

            # Serialize ticket details
            ticket_data = TicketSerializer(tickets, many=True).data

            # Combine event and ticket details
            data = {
                'event': event_data,
                'tickets': ticket_data
            }

            return Response(data, status=status.HTTP_200_OK)

        except Event.DoesNotExist as e:
            # Handle case where no active event is found
            print(f"Event not found: {e}")
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        except Ticket.DoesNotExist as e:
            # Handle case where no tickets are available for the event
            print(f"Ticket not found: {e}")
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        except ValueError as e:
            # Handle any ValueErrors that could occur (e.g., invalid data in query params)
            print(f"Value error: {e}")
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Log any unexpected exceptions and return a generic error response
            print(f"An unexpected error occurred: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class CreateProfileAndBookingView(APIView):

    @transaction.atomic
    def post(self, request):
        try:
            
            profile_data = {
                'name': request.data.get('name'),
                'age': request.data.get('age'),
                'mobile': request.data.get('mobile'),
                'email': request.data.get('email'),
                'gender': request.data.get('gender')
            }


            booking_data = {
                'event': request.data.get('event'), 
                'ticket': request.data.get('ticket'),  
                'ticket_quantity': request.data.get('ticket_quantity'),
                'attending_time': request.data.get('attending_time'),
                'cab_facility_required': request.data.get('cab_facility_required', False),
                'location': request.data.get('location', ''),
                'address': request.data.get('address', '')
            }

            # Validate and save Profile
            profile_serializer = ProfileSerializer(data=profile_data)
            if profile_serializer.is_valid(raise_exception=True):
                print('----------------- Profile data is correct ------------------------')
                mobile = profile_serializer.validated_data.get('mobile')
                if not User.objects.filter(mobile=mobile).exists():
                    return Response({'error': 'User with this mobile number does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    print('----------------- User exists ------------------------')
                    user = User.objects.get(mobile = mobile)
                    if not Profile.objects.filter(user=user).exists():
                        print('saving user profile...')
                        profile = profile_serializer.save(user=user)

            # Validate and save EventBooking
            print('-------------------- booking data ----------------- ')
            print(booking_data)
            booking_serializer = EventBookingSerializer(data=booking_data)
            if booking_serializer.is_valid(raise_exception=True):
                print('----------------- Profile data is correct in booking ------------------------')
                mobile = profile_serializer.validated_data.get('mobile')
                if not User.objects.filter(mobile=mobile).exists():
                    return Response({'error': 'User with this mobile number does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    print('----------------- User exists in booking ------------------------')
                    user = User.objects.get(mobile = mobile)
                    # event_booking = booking_serializer.save(user=user)

            ticket_price = booking_serializer.validated_data.get('ticket').price
            ticket_amount = ticket_price * booking_serializer.validated_data.get('ticket_quantity')

            reference_id = str(uuid.uuid4())

            razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))

            payment_details = razorpay_client.payment_link.create({
                                "amount": 100,
                                "currency": "INR",
                                "description": "For Hydrovibe 2024",
                                "customer": {
                                    "name": profile_serializer.validated_data.get('name'),
                                    "contact": profile_serializer.validated_data.get('mobile')
                                },
                                "notify": {
                                    "sms": True
                                },
                                "reminder_enable": True,
                                "notes": {
                                    "event_name": "Hydrovide 2024"
                                },
                                "reference_id": reference_id,
                                "callback_url": "http://localhost:8000/event-registration/callback-for-razorpay",
                                "callback_method": "get"
                                })
            print('------------- payment details ------------------- ', payment_details)
            print(' ----------------- ticket amount ------------- ', ticket_amount)
            print('--------------------------- profile serializer data ----------- ', profile_serializer.validated_data)
            print('--------------------------- booking serializer data ----------- ', booking_serializer.validated_data)
            
            event = booking_serializer.validated_data.get('event')
            ticket = booking_serializer.validated_data.get('ticket')
            ticket_quantity = booking_serializer.validated_data.get('ticket_quantity')
            attending_time = booking_serializer.validated_data.get('attending_time')
            cab_facility_required = booking_serializer.validated_data.get('cab_facility_required')
            location = booking_serializer.validated_data.get('location')
            address = booking_serializer.validated_data.get('address')
            formis_payment_id = reference_id
            vendor_payment_id = payment_details.get('id')
            payment_amount = ticket_amount
            payment_link = payment_details.get('short_url')

            event_booking = EventBooking(event=event, user=user, ticket=ticket, ticket_quantity=ticket_quantity,
                                         attending_time=attending_time, cab_facility_required=cab_facility_required,
                                         location=location, address=address, formis_payment_id=formis_payment_id,
                                         vendor_payment_id=vendor_payment_id, payment_amount=payment_amount, payment_link=payment_link)
            
            event_booking.save()

            return Response(

                {
                    'id': formis_payment_id,
                    'payment_link': payment_link
                },
                status=status.HTTP_201_CREATED
            )

        except ObjectDoesNotExist as e:
            print(f"Object not found: {e}")
            return Response({'error': 'Event or ticket not found'}, status=status.HTTP_404_NOT_FOUND)

        except ValueError as e:
            print(f"Value error: {e}")
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"Unexpected error: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class CallbackForPaymentGateway(APIView):

    def get(self, request):

        razorpay_payment_id = request.query_params.get('razorpay_payment_id')
        razorpay_payment_link_reference_id = request.query_params.get('razorpay_payment_link_reference_id')

        event_booking = EventBooking.objects.filter(formis_payment_id = razorpay_payment_link_reference_id).first()

        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))

        razorpay_payment_status = razorpay_client.payment.fetch(razorpay_payment_id)

        captured = razorpay_payment_status.get('captured')

        if captured:
            
            event_booking.vendor_payment_id = razorpay_payment_id
            event_booking.payment_completed = True
            event_booking.payment_completed_at = datetime.datetime.fromtimestamp(razorpay_payment_status.get('created_at'))
            event_booking.save()
        else:

            print(razorpay_payment_status)

        return redirect('https://www.google.com')
    

class CheckPaymentStatus(APIView):

    def get(self, request):

        reference_id = request.query_params.get('reference_id')

        event_booking = EventBooking.objects.filter(formis_payment_id = reference_id).first()

        if event_booking.payment_completed:

            data = {
                'payment_completed': True
            }

        else:

            data = {
                'payment_completed': False
            }

        return Response(data=data, status=status.HTTP_200_OK)