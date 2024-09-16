import random
from rest_framework_simplejwt.tokens import RefreshToken

def generate_otp():

    return random.randint(100000, 999999)

def generate_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }