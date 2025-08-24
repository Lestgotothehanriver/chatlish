from django.conf import settings
#________________________________________________________________
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
# contenttypes는 Django에서 모델의 관계를 동적으로 정의할 수 있게 해주는 기능으로, 
# GenericForeignKey를 사용하면 어떤 모델의 인스턴스도 참조할 수 있게 해줍니다.
#________________________________________________________________
from django.db import models
from django.db.models import Q
#________________________________________________________________

# 커스텀 유저 모델을 불러오기 위한 설정값. 보통은 auth.User 또는 직접 정의한 User 모델이 됨
from django.conf import settings
from chatchat.apps.user_app.models import User

#_______________________________________________________________________
# ✅ ChatRoomManager: 채팅방을 쉽게 만들 수 있게 도와주는 매니저
#_______________________________________________________________________
class ChatRoomManager(models.Manager):
    def create_room(self, related_obj=None, participants=None, title=""):
        """
        관련된 객체(Post 등)와 참가자들을 기반으로 채팅방을 생성하는 헬퍼 함수
        """
        room = self.model(title=title)  # 일단 제목만 있는 빈 방 생성

        if related_obj:
            # 만약 관련된 객체(Post, Article 등)가 있다면 content_type, object_id를 설정
            room.content_type = ContentType.objects.get_for_model(related_obj)
            room.object_id    = related_obj.pk

        room.save()  # 방을 먼저 저장해야 ManyToManyField를 추가할 수 있음

        if participants:
            # 참가자들을 ManyToMany 필드에 추가
            room.participants.add(*participants)

        room.save()  # 참가자 추가 후 다시 저장

        return room


#_______________________________________________________________________
# ✅ ChatRoom 모델: DM 또는 그룹 채팅방
#_______________________________________________________________________
class ChatRoom(models.Model):
    participants = models.ManyToManyField(User, related_name="chat_rooms")
    # 이 방에 참가하는 유저들. 여러 명이 들어올 수 있어서 ManyToMany 사용

    title        = models.CharField(max_length=255, blank=True)
    # 그룹방 이름. DM이면 비워둘 수도 있음

    content_type = models.ForeignKey(ContentType, null=True, blank=True,
                                     on_delete=models.SET_NULL)
    object_id    = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    # 위 두 필드를 조합해서 이 방이 어떤 모델(Post 등)을 참조하는지 설정
    # 예: 중고거래 게시글에 연결된 채팅방

    created_at   = models.DateTimeField(auto_now_add=True)
    # 채팅방이 생성된 시간

    objects = ChatRoomManager()
    # 기본 매니저 대신 우리가 만든 Manager를 붙임 → create_room 같은 함수 사용 가능

    def __str__(self):
        return self.title or f"Room {self.pk}"
        # 제목이 있으면 제목, 없으면 "Room 1"처럼 출력


#_______________________________________________________________________
# ✅ ChatMessage 모델: 채팅방 안의 메시지
#_______________________________________________________________________
class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, related_name="messages",
                             on_delete=models.CASCADE)
    # 이 메시지가 어떤 채팅방에 속해 있는지

    sender = models.ForeignKey(User, related_name="sent_messages",
                               on_delete=models.CASCADE)
    # 누가 보낸 메시지인지

    text = models.TextField(blank=True)
    # 메시지 텍스트. 파일만 보낼 수도 있어서 blank=True

    read_by = models.ManyToManyField(User, blank=True,
                                     related_name="read_messages")
    # 이 메시지를 읽은 유저들 목록 (읽음 처리용)

    created_at = models.DateTimeField(auto_now_add=True)
    # 메시지가 생성된 시간

    class Meta:
        ordering = ("created_at",)
        # 메시지 가져올 때 오래된 순서로 정렬됨 (room.messages.all() 하면 자동 정렬)

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # 아직 저장되지 않은 새 메시지인지 확인
        super().save(*args, **kwargs)

        if is_new:
            # 새 메시지라면, 보낸 사람은 자동으로 '읽은 사람 목록'에 추가
            self.read_by.add(self.sender)

#_______________________________________________________________________
# ✅ Image 모델: 채팅방에서 사용되는 이미지 첨부
#_______________________________________________________________________
class Image(models.Model):
    """
    채팅방에서 사용되는 이미지 첨부 모델
    """
    message = models.ForeignKey(ChatMessage, related_name="images",
                             on_delete=models.CASCADE, null=True, blank=True)
    # 이 이미지가 어떤 채팅방에 속하는지

    image = models.ImageField(upload_to="chat/images/")
    # 이미지 파일. 업로드 경로 지정

    uploaded_at = models.DateTimeField(auto_now_add=True)
    # 이미지 업로드 시간

#_______________________________________________________________________
# ✅ UserDeviceToken 모델: 사용자 디바이스 토큰, 단말 푸시 토큰을 저장한다
#_______________________________________________________________________
class UserDeviceToken(models.Model):
    user = models.OneToOneField(User, related_name="device_token",
                                  on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user_id}:{self.platform}"


# apps/chat/models.py  (기존 파일에 이어서)
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from chatchat.apps.user_app.models import User
from .models import ChatRoom  # 이미 있는 모델

class MatchTicket(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        MATCHED = "MATCHED", "Matched"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="match_tickets")
    party_size = models.PositiveIntegerField()  # 유저가 원하는 총 인원 수 (ex. 2, 3, 4...)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    chat_room = models.ForeignKey(ChatRoom, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [
            models.Index(fields=["status", "party_size", "created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user_id}-{self.party_size}-{self.status}"

class MatchGroup(models.Model):
    party_size = models.PositiveIntegerField()
    members = models.ManyToManyField(User, related_name="match_groups")
    chat_room = models.OneToOneField(ChatRoom, on_delete=models.CASCADE, related_name="match_group")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"group({self.id}) size={self.party_size}"


