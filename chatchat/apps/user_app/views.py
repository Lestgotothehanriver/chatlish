from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import User, PendingSignup
from .serializers import UserSerializer, RegisterSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
import secrets
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import transaction
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.shortcuts import render
from rest_framework.decorators import action
#______________________________________________________
from .utils.firebase import verify_app_check
#______________________________________________________

