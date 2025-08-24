from django.contrib import admin
from .models import ChatRoom, ChatMessage, Image, UserDeviceToken

admin.site.register(ChatRoom)
admin.site.register(ChatMessage)
admin.site.register(Image)
admin.site.register(UserDeviceToken)
# Register your models here.
