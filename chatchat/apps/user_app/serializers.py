from rest_framework import serializers
from .models import User, PendingSignup
from .models import DEPARTMENTS
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

UserModel = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserModel
        fields = ("id", "username", "password", "email", "gender",
                  , "profile_img", "birth_date", 
                  "name", "nickname", "is_authenticated")
        extra_kwargs = {"password": {"write_only": True}}
        read_only_fields = ("is_authenticated",)

    def create(self, validated_data):
        validated_data["password"] = make_password(validated_data["password"])
        return super().create(validated_data)

class NicknameSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id","nickname",)

