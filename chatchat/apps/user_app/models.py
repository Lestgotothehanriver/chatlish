
# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets


class User(AbstractUser):
    # username, email, password, first_name, last_name, is_staff, is_active, date_joined, last_login 등이 자동으로 생성됨
    GENDER = (("남", "Male"), ("여", "Female"))
    gender      = models.CharField(max_length=1, choices=GENDER, blank=True, null=True)
    profile_img = models.ImageField(upload_to="profile/", blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    nickname = models.CharField(max_length=100, blank=True, null=True)
    is_email_verified = models.BooleanField(default=False, blank=True, null=True)

    def __str__(self):
        return self.username

