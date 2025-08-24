from django.urls import path, re_path
from .consumers import ChatConsumer, MatchConsumer
print("✅ [Routing] WebSocket URL patterns loaded")
websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<room_id>\d+)/(?P<user_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"ws/match/$", MatchConsumer.as_asgi()),  # 추가
]