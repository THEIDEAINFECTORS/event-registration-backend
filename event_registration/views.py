from rest_framework.exceptions import ValidationError
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
from .utility import generate_otp, generate_tokens_for_user
import uuid
import razorpay
import datetime
from django.shortcuts import redirect
import qrcode
import base64
from io import BytesIO
from rest_framework_simplejwt.serializers import TokenVerifySerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()

class SendOTP(APIView):

    def post(self, request):
        try:

            serializer = SendOTPSerializer(data=request.data)
            if serializer.is_valid():
                mobile_number = serializer.validated_data['mobile']
                
                user, created = User.objects.get_or_create(mobile=mobile_number)

                otp = generate_otp()

                expires_at = timezone.now() + timedelta(minutes=10)

                OTP.objects.create(user=user, otp=otp, created_at=timezone.now(), exprires_at=expires_at, active=True)

                client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

                message = client.messages.create(
                    body=f'Your Kitsa Hydrovibe 2024 code is {otp}',
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
        except ValidationError as e:
            print(f'Validation Error: {e} ')
            return Response({'error': 'Validation Error'})
        except ValueError as e:
            print(f"Value error: {e}")
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class VerifyOTP(APIView):

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            mobile_number = serializer.validated_data['mobile']
            otp_input = serializer.validated_data['otp']

            try:
                user = User.objects.get(mobile=mobile_number)
                
                otp_record = OTP.objects.filter(user=user, active=True).latest('created_at')
                
                if otp_record.otp == otp_input:
                    if otp_record.exprires_at >= timezone.now():
                        otp_record.active = False
                        otp_record.save()

                        tokens = generate_tokens_for_user(user)
                        event_booking = EventBooking.objects.filter(user=user, payment_completed=True).first()

                        if event_booking:
                            qr_data = {
                                    'payment_completed': True,
                                    'event_id': event_booking.event.id,
                                    'user': event_booking.user.mobile,
                                    'ticket': event_booking.ticket.name,
                                    'ticket_quantity': event_booking.ticket_quantity,
                                    'attending_time': event_booking.attending_time,
                                    'cab_facility_required': event_booking.cab_facility_required,
                                    'payment_completed': event_booking.payment_completed,
                                    'reference_id': event_booking.formis_payment_id
                                }

                            qr = qrcode.QRCode(
                                version=1,
                                error_correction=qrcode.constants.ERROR_CORRECT_L,
                                box_size=10,
                                border=4,
                            )
                            qr.add_data(qr_data)
                            qr.make(fit=True)

                            img = qr.make_image(fill='black', back_color='white')

                            # Save the image to a BytesIO object
                            buffer = BytesIO()
                            img.save(buffer, format="PNG")
                            buffer.seek(0)

                            # Encode the image to base64
                            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

                            return Response({"message": "OTP verified successfully!", "ticket": img_str, 'access': tokens['access'],
                                            'refresh': tokens['refresh']}, status=status.HTTP_200_OK)

                        
                        return Response({"message": "OTP verified successfully!", "ticket": None, 'access': tokens['access'],
                                        'refresh': tokens['refresh']}, status=status.HTTP_200_OK)
                    else:
                        return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)
            except ValidationError as e:
                print(f'Validation Error: {e} ')
                return Response({'error': 'Validation Error'})
            
            except User.DoesNotExist:
                return Response({"error": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)
            except OTP.DoesNotExist:
                return Response({"error": "No active OTP found for this user."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LatestActiveEventView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            event = Event.objects.filter(active=True, event_date__gte=timezone.now().date()).order_by('event_date').first()

            if not event:
                raise Event.DoesNotExist("No active event available")

            event_data = EventSerializer(event).data

            tickets = Ticket.objects.filter(event=event).distinct()

            if not tickets.exists():
                raise Ticket.DoesNotExist("No tickets available for this event")

            total_available_tickets = sum(ticket.total_tickets_available for ticket in tickets)

            if total_available_tickets == 0:
                raise Ticket.DoesNotExist("No tickets available for this event")

            ticket_data = TicketSerializer(tickets, many=True).data

            data = {
                'event': event_data,
                'tickets': ticket_data
            }

            return Response(data, status=status.HTTP_200_OK)
        except ValidationError as e:
            print(f'Validation Error: {e} ')
            return Response({'error': 'Validation Error'})

        except Event.DoesNotExist as e:
            print(f"Event not found: {e}")
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        except Ticket.DoesNotExist as e:
            print(f"Ticket not found: {e}")
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        except ValueError as e:
            print(f"Value error: {e}")
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class CreateProfileAndBookingView(APIView):

#     permission_classes = [IsAuthenticated]
    
#     @transaction.atomic
#     def post(self, request):
#         try:
            
#             profile_data = {
#                 'name': request.data.get('name'),
#                 'age': request.data.get('age'),
#                 'mobile': request.data.get('mobile'),
#                 'email': request.data.get('email'),
#                 'gender': request.data.get('gender')
#             }

#             booking_data = {
#                 'event': request.data.get('event'), 
#                 'ticket': request.data.get('ticket'),  
#                 'ticket_quantity': request.data.get('ticket_quantity'),
#                 'attending_time': request.data.get('attending_time'),
#                 'cab_facility_required': request.data.get('cab_facility_required', False),
#                 'location': request.data.get('location', ''),
#                 'address': request.data.get('address', '')
#             }

#             profile_serializer = ProfileSerializer(data=profile_data)
#             profile_serializer.is_valid(raise_exception=True)
#             mobile = profile_serializer.validated_data.get('mobile')

#             user = User.objects.filter(mobile=mobile).first()
#             if not user:
#                 return Response({'error': 'User with this mobile number does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

#             profile, created = Profile.objects.get_or_create(user=user, defaults=profile_serializer.validated_data)

#             booking_serializer = EventBookingSerializer(data=booking_data)
#             booking_serializer.is_valid(raise_exception=True)

#             ticket_price = booking_serializer.validated_data['ticket'].price
#             ticket_quantity = booking_serializer.validated_data['ticket_quantity']
#             ticket_amount = ticket_price * ticket_quantity

#             reference_id = str(uuid.uuid4())

#             try:
#                 scheme = request.scheme
#                 host = request.get_host()
#                 full_url = f"{scheme}://{host}"
#                 razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))
#                 payment_details = razorpay_client.payment_link.create({
#                                 "amount": ticket_amount * 100,
#                                 "currency": "INR",
#                                 "description": "For Hydrovibe 2024",
#                                 "customer": {
#                                     "name": profile_serializer.validated_data.get('name'),
#                                     "contact": profile_serializer.validated_data.get('mobile')
#                                 },
#                                 "notify": {
#                                     "sms": True
#                                 },
#                                 "reminder_enable": True,
#                                 "notes": {
#                                     "event_name": "Hydrovide 2024"
#                                 },
#                                 "reference_id": reference_id,
#                                 "callback_url": f"{full_url}/event-registration/callback-for-razorpay",
#                                 "callback_method": "get"
#                                 })
#             except razorpay.errors.RazorpayError as e:
#                 print(f"Razorpay error: {e}")
#                 return Response({'error': 'Failed to create payment link'}, status=status.HTTP_502_BAD_GATEWAY)

#             event_booking = EventBooking(
#                 event=booking_serializer.validated_data['event'],
#                 user=user,
#                 ticket=booking_serializer.validated_data['ticket'],
#                 ticket_quantity=booking_serializer.validated_data['ticket_quantity'],
#                 attending_time=booking_serializer.validated_data['attending_time'],
#                 cab_facility_required=booking_serializer.validated_data.get('cab_facility_required', False),
#                 location=booking_serializer.validated_data.get('location', ''),
#                 address=booking_serializer.validated_data.get('address', ''),
#                 formis_payment_id=reference_id,
#                 vendor_payment_id=payment_details.get('id'),
#                 payment_amount=ticket_amount,
#                 payment_link=payment_details.get('short_url')
#             )
#             event_booking.save()

#             return Response(
#                 {
#                     'id': reference_id,
#                     'payment_link': payment_details.get('short_url')
#                 },
#                 status=status.HTTP_201_CREATED
#             )

#         except ValidationError as e:
#             error_details = e.detail
#             unique_error_messages = []

#             if 'event' in error_details and 'unique' in error_details['event'][0].code:
#                 unique_error_messages.append('An event booking with this event already exists.')
            
#             if 'ticket' in error_details and 'unique' in error_details['ticket'][0].code:
#                 unique_error_messages.append('An event booking with this ticket already exists.')

#             if unique_error_messages:
#                 return Response({'error': unique_error_messages}, status=status.HTTP_400_BAD_REQUEST)

#             return Response({'error': error_details}, status=status.HTTP_400_BAD_REQUEST)
        

#         except ObjectDoesNotExist as e:
#             print(f"Object not found: {e}")
#             return Response({'error': 'Event or ticket not found'}, status=status.HTTP_404_NOT_FOUND)

#         except ValueError as e:
#             print(f"Value error: {e}")
#             return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

#         except Exception as e:
#             print(f"Unexpected error: {e}")
#             return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateProfileAndBookingView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        try:
            user = request.user  # Fetch the user from the token

            print('------------ request data ----------- ', request.data)

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
                'cab_facility_required': request.data.get('cab_facility_required', False)
            }

            print('Profile serializer...')

            # Validate and save Profile
            profile_serializer = ProfileSerializer(data=profile_data)
            profile_serializer.is_valid(raise_exception=True)
            print('Profile serializer done...')
            # No need to fetch user from the database using mobile number, as user is already available
            profile, created = Profile.objects.get_or_create(user=user, defaults=profile_serializer.validated_data)
            print('Profile serializer created...')
            # Validate and save EventBooking
            print('booking serializer...')
            booking_serializer = EventBookingSerializer(data=booking_data)
            
            try:
                booking_serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                # Print the exception message
                print("Validation Error:", e)
                # Optionally, you can print the detailed error dictionary
                print("Detailed Error:", e.detail)
            print('Profile serializer done...')

            ticket_price = booking_serializer.validated_data['ticket'].price
            ticket_quantity = booking_serializer.validated_data['ticket_quantity']
            ticket_amount = ticket_price * ticket_quantity
            print('Ticket amount...')
            reference_id = str(uuid.uuid4())

            # Create payment link
            try:
                scheme = request.scheme
                host = request.get_host()
                full_url = f"{scheme}://{host}"
                razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))
                payment_details = razorpay_client.payment_link.create({
                                "amount": ticket_amount * 100,
                                "currency": "INR",
                                "description": "For Hydrovibe 2024",
                                "customer": {
                                    "name": profile_serializer.validated_data['name'],
                                    "contact": profile_serializer.validated_data['mobile']
                                },
                                "notify": {
                                    "sms": True
                                },
                                "reminder_enable": True,
                                "notes": {
                                    "event_name": "Hydrovibe 2024"
                                },
                                "reference_id": reference_id,
                                "callback_url": f"{full_url}/event-registration/callback-for-razorpay",
                                "callback_method": "get"
                                })
            except Exception as e:
                print('Exception in creating payment link : ', e)
                return Response({'error': 'Failed to create payment link'}, status=status.HTTP_502_BAD_GATEWAY)

            # Save EventBooking
            event_booking = EventBooking(
                event=booking_serializer.validated_data['event'],
                user=user,
                ticket=booking_serializer.validated_data['ticket'],
                ticket_quantity=booking_serializer.validated_data['ticket_quantity'],
                attending_time=booking_serializer.validated_data['attending_time'],
                cab_facility_required=booking_serializer.validated_data.get('cab_facility_required', False),
                location=booking_serializer.validated_data.get('location', ''),
                address=booking_serializer.validated_data.get('address', ''),
                formis_payment_id=reference_id,
                vendor_payment_id=payment_details.get('id'),
                payment_amount=ticket_amount,
                payment_link=payment_details.get('short_url')
            )
            event_booking.save()

            return Response(
                {
                    'id': reference_id,
                    'payment_link': payment_details.get('short_url')
                },
                status=status.HTTP_201_CREATED
            )

        except ValidationError as e:
            error_details = e.detail
            unique_error_messages = []

            if 'event' in error_details and 'unique' in error_details['event'][0].code:
                unique_error_messages.append('An event booking with this event already exists.')
            
            if 'ticket' in error_details and 'unique' in error_details['ticket'][0].code:
                unique_error_messages.append('An event booking with this ticket already exists.')

            if unique_error_messages:
                return Response({'error': unique_error_messages}, status=status.HTTP_400_BAD_REQUEST)
            print('Validation Error --- ', e)
            return Response({'error': error_details}, status=status.HTTP_400_BAD_REQUEST)

        except ObjectDoesNotExist as e:
            print('Object does not exist --- ', e)
            return Response({'error': 'Event or ticket not found'}, status=status.HTTP_404_NOT_FOUND)

        except ValueError as e:
            print('Value Error --- ', e)
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print('Internal server error --- ', e)
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    

class CallbackForPaymentGateway(APIView):

    def get(self, request):
        try:


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
        except ValueError as e:
            print(f"Value error: {e}")
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"Unexpected error: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class CheckPaymentStatus(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:

            reference_id = request.query_params.get('reference_id')

            event_booking = EventBooking.objects.filter(formis_payment_id = reference_id).first()

            

            qr_data = {
                    'payment_completed': True,
                    'event_id': event_booking.event.id,
                    'user': event_booking.user.mobile,
                    'ticket': event_booking.ticket.name,
                    'ticket_quantity': event_booking.ticket_quantity,
                    'attending_time': event_booking.attending_time,
                    'cab_facility_required': event_booking.cab_facility_required,
                    'payment_completed': event_booking.payment_completed,
                    'reference_id': event_booking.formis_payment_id
                }

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)

            img = qr.make_image(fill='black', back_color='white')

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

            if event_booking.payment_completed:
                data = {
                    'payment_completed': True,
                    'ticket': img_str
                }

            else:
                data = {
                    'payment_completed': False,
                    'ticket': img_str
                }

            return Response(data=data, status=status.HTTP_200_OK)
        except ValueError as e:
            print(f"Value error: {e}")
            return Response({'error': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"Unexpected error: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class VerifyTokenView(APIView):
    def post(self, request):
        serializer = TokenVerifySerializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            token = request.data.get('token')

            decoded_token = UntypedToken(token)
            user_id = decoded_token['user_id']

            # Fetch user from the database
            user = User.objects.get(id=user_id)
            return Response({'message': 'Token is valid', 'mobile': user.mobile}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({'error': 'Token is invalid or expired'}, status=status.HTTP_401_UNAUTHORIZED)
        
class RefreshTokenView(APIView):
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({'error': 'Invalid refresh token or token expired'}, status=status.HTTP_401_UNAUTHORIZED)
        
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')

            if not refresh_token:
                return Response({'error': 'refresh tokens is required'}, status=status.HTTP_400_BAD_REQUEST)


            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError as e:
                return Response({'error': f'Error blacklisting refresh token: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

            return Response({'message': 'Successfully logged out'}, status=status.HTTP_205_RESET_CONTENT)

        except ObjectDoesNotExist as e:
            print(f"Object not found: {e}")
            return Response({'error': 'Invalid tokens'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"Unexpected error: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserEventBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user

            event_booking = EventBooking.objects.filter(user=user).first()

            if not event_booking:
                return Response({'message': 'No bookings found for this user.'}, status=status.HTTP_404_NOT_FOUND)
            
            booking_serializer = EventBookingSerializer(event_booking)

            booking_data = {
                    'payment_completed': event_booking.payment_completed,
                    'event_id': event_booking.event.id,
                    'user': event_booking.user.mobile,
                    'ticket': event_booking.ticket.name,
                    'ticket_quantity': event_booking.ticket_quantity,
                    'attending_time': event_booking.attending_time,
                    'cab_facility_required': event_booking.cab_facility_required,
                    'payment_completed': event_booking.payment_completed,
                    'reference_id': event_booking.formis_payment_id,
                    'payment_link': event_booking.payment_link,
                    'name': request.user.profile.name
                }

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(booking_data)
            qr.make(fit=True)

            img = qr.make_image(fill='black', back_color='white')

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')


            
            return Response({'data': booking_data, 'qr': img_str}, status=status.HTTP_200_OK)

        except ObjectDoesNotExist as e:
            print(f"Object not found: {e}")
            return Response({'error': 'Event booking not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(f"Unexpected error: {e}")
            return Response({'error': 'Something went wrong. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)