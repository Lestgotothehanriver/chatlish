"""
ASGI config for uniway project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

# 필수 모듈 가져오기 (운영체제와 장고 초기화용)
import os, django

# 장고 설정 파일 위치를 알려주고,
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatchat.settings")
# 장고를 사용할 수 있도록 준비시킴 (모델, ORM 등 다 이때 활성화됨)
django.setup()
# Starlette는 Django와 함께 사용할 수 있는 ASGI 프레임워크
from starlette.applications import Starlette  # Starlette 애플리케이션

# Mount import 해오기
from starlette.routing import Mount  # Starlette 라우팅 기능
from starlette.staticfiles import StaticFiles  # 정적 파일 서빙용


# Channels에서 웹소켓 인증 처리와 라우팅 기능을 가져옴
from channels.auth import AuthMiddlewareStack       # 로그인 유저 확인해주는 애
from channels.routing import ProtocolTypeRouter, URLRouter  # 요청 타입에 따라 분기해주는 애, 라우터
from django.core.asgi import get_asgi_application 
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
# 웹소켓 주소 모음 (채팅방 주소들)
from chatchat.apps.chat_app.routing import websocket_urlpatterns
print("✅ [ASGI] Application loaded")
# ASGI application 설정

django_app = get_asgi_application()
star_app = Starlette(routes=[
    # /media/* -> Starlette StaticFiles
    Mount("/media", app=StaticFiles(directory=str(settings.MEDIA_ROOT)), name="media"),
    Mount("/static", app=StaticFiles(directory=str(settings.STATIC_ROOT)), name="static"),
    # 나머지 모든 http -> Django
    Mount("/", app=django_app),
])
application = ProtocolTypeRouter({
    # 일반 HTTP 요청은 Django 기본 처리기로 보냄 (회원가입, 로그인 등)
    "http": star_app,
    # 웹소켓 요청은 다음 과정을 거침:
    # 1. 로그인한 유저인지 확인 (AuthMiddlewareStack)
    # 2. 웹소켓 주소를 보고 어디로 보낼지 정함 (URLRouter)
    # 3. 실제 소비자(consumer)가 이걸 받아서 처리함 (채팅방 연결 등)
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
