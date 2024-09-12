from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    """
    Custom manager for User model where mobile number is the unique identifier
    for authentication instead of username or email.
    """

    def create_user(self, mobile, password=None, **extra_fields):
        """
        Create and return a regular user with a mobile number and password.
        """
        if not mobile:
            raise ValueError(_('The Mobile number must be set'))

        # Normalize mobile number (optional, depending on your app's needs)
        mobile = self.normalize_mobile(mobile)  
        user = self.model(mobile=mobile, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, mobile, password=None, **extra_fields):
        """
        Create and return a superuser with a mobile number and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(mobile, password, **extra_fields)

    def normalize_mobile(self, mobile):
        """
        Optional: Normalize the mobile number, e.g., removing spaces, dashes, etc.
        Customize this method according to your needs.
        """
        return mobile.strip()
    
class User(AbstractBaseUser, PermissionsMixin):
    mobile = models.CharField(max_length=15, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = []  # Specify other required fields here

    def __str__(self):
        return self.mobile

class OTP(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    otp = models.PositiveIntegerField(null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    exprires_at = models.DateTimeField(null=False)
    active = models.BooleanField(default=False)

    def __str__(self):

        return f'{self.user} - {self.otp}'

class Event(models.Model):

    name = models.CharField(max_length=200, null=False)
    event_date = models.DateField(null=False)
    event_start_time = models.TimeField(null=False)
    event_end_time = models.TimeField(null=False)
    active = models.BooleanField(default=False)

    def __str__(self):

        return f'{self.name} - {self.event_date}'

class Ticket(models.Model):

    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=20, null=False)
    price = models.PositiveIntegerField(null=False)
    total_tickets = models.PositiveIntegerField(null=False)
    total_tickets_available = models.PositiveIntegerField(null=False)

    def __str__(self):

        return f'{self.name} - {self.event.name}'


class Profile(models.Model):

    AGE_OPTIONS = (
        ('18-24', '18-24'),
        ('25-40', '25-40'),
        ('41-55', '41-55'),
        ('55+', '55+')
    )

    GENDER_OPTIONS = (
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Rather Not To Say', 'Rather Not To Say')
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=150, null=False)
    age = models.CharField(choices=AGE_OPTIONS, null=False, max_length=10)
    mobile = models.PositiveBigIntegerField(null=False)
    email = models.EmailField(null=True)
    gender = models.CharField(choices=GENDER_OPTIONS, null=False, max_length=20)

    def __str__(self):

        return self.name


class EventBooking(models.Model):

    ATTENDING_TIME = (
        ('4PM-8PM', '4PM-8PM'),
        ('8PM-12PM', '8PM-12PM')
    )

    event = models.OneToOneField(Event, on_delete=models.CASCADE, null=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=False)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, null=False)
    ticket_quantity = models.PositiveIntegerField(null=False)
    attending_time = models.CharField(choices=ATTENDING_TIME, null=False, max_length=10)
    cab_facility_required = models.BooleanField(default=False)
    location = models.CharField(max_length=50, null=True)
    address = models.CharField(max_length=400, null=True)
    formis_payment_id = models.CharField(max_length=20, null=True)
    vendor_payment_id = models.CharField(max_length=50, null=True)
    payment_amount = models.FloatField()
    payment_link = models.URLField()
    payment_completed = models.BooleanField(default=False)
    payment_completed_at = models.DateTimeField(null=True)

    def __str__(self):

        return f'{self.event.name} - {self.user.mobile} - {self.ticket_quantity}'



