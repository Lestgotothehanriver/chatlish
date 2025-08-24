from rest_framework import serializers
from .models import ChatRoom, ChatMessage, Image


class ImageSerializer(serializers.ModelSerializer):
    """
    이미지 모델을 직렬화하는 클래스.
    """
    class Meta:
        model = Image
        fields = ('id', 'image')
        read_only_fields = ('id',)  # ID는 읽기 전용

class ChatMessageSerializer(serializers.ModelSerializer):
    # 모델에는 없는 필드지만, 직접 계산해서 응답에 포함시킴
    # 첨부파일이 있을 경우 해당 파일의 URL 반환   
    # 모델에는 없지만, 이 메시지를 읽은 사람 수를 계산해서 응답에 포함
    read_count     = serializers.SerializerMethodField()
    sender_nickname = serializers.CharField(source='sender.nickname', read_only=True)
    images = ImageSerializer(many=True, read_only=True)
    
    #필드 이름이 xxx = serializers.SerializerMethodField()이면
    #함수 이름은 get_xxx(self, obj)로 정의해야 함.

    class Meta:
        model = ChatMessage
        fields = (
            "id",              # 메시지 고유 ID
            "room",            # 어떤 채팅방에 속한 메시지인지
            "sender",          # 누가 보낸 메시지인지 (User 객체)
            "sender_nickname",# 보낸 사람의 닉네임 (읽기 전용)
            "text",            # 메시지 텍스트 내용
            "read_by",         # 누가 읽었는지 (ManyToManyField)
            "read_count",      # 읽은 사람 수 (계산됨)
            "created_at",      # 메시지 생성 시각
            "images",         # 첨부된 이미지들 (ManyToManyField)
        )

        # 사용자가 직접 수정하거나 보낼 수 없는 읽기 전용 필드 지정
        read_only_fields = (
            "sender", "read_by", "attachment_url",
            "read_count", "created_at", 
        )

    def get_read_count(self, obj):
        """
        이 메시지를 읽은 사람의 수를 반환.
        read_by는 ManyToManyField이므로 .count()로 계산 가능.
        """
        return obj.read_by.count()

class ChatRoomListSerializer(serializers.ModelSerializer):
    # 해당 채팅방에서 오간 메시지들을 포함해서 응답에 보여줌
    # read_only=True: 메시지를 API로 수정하거나 생성하진 않음
    content_type_info = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    participants_profile_imgs = serializers.SerializerMethodField()
    not_read_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = (
            "id",           # 채팅방 고유 ID
            "title",        # 채팅방 제목 (예: 그룹명)
            "participants", # 채팅방 참가자들 (ManyToManyField)
            "created_at",   # 방 생성 시간
            "content_type_info",  # 연결된 모델 정보 (예: 게시글)
            "last_message",  # 채팅방의 마지막 메시지
            "participants_profile_imgs",  # 참가자들의 프로필 이미지 URL
            "not_read_count",  # 읽지 않은 메시지 수
        )
        # 생성 시간은 사용자가 수정할 수 없게 읽기 전용으로 설정
        read_only_fields = ("created_at",)

    def get_content_type_info(self, obj):
        """
        연결된 모델(Post 등)의 정보 반환.
        content_type과 object_id를 조합해서 어떤 모델인지 알 수 있음.
        """
        if obj.content_type:
            return {
                "id": obj.object_id,
                "title": obj.content_object.title if obj.content_object else None,
                "content_type": obj.content_object._meta.model_name  # 모델 이름

            }
        return None

    def get_last_message(self, obj):
        """
        채팅방의 마지막 메시지를 반환.
        없으면 None을 반환.
        """
        last_message = obj.messages.last()
        if last_message:
            return {
                "text": last_message.text,
                "sender": last_message.sender.nickname,  # 보낸 사람의 닉네임
                "created_at": last_message.created_at,
            }

    def get_participants_profile_imgs(self, obj):
        """
        채팅방 참가자들의 프로필 이미지 URL을 최대 4개 반환.
        """
        profile_imgs = []
        for participant in obj.participants.all()[:4]:
            if participant.profile_img:
                profile_imgs.append(participant.profile_img.url)
            else:
                profile_imgs.append(None)

        return profile_imgs

    def get_not_read_count(self, obj):
        """
        현재 사용자가 읽지 않은 메시지 수를 반환.
        """
        user = self.context['request'].user
        read_count = obj.messages.filter(
            read_by=user
        ).count()
        total_count = obj.messages.count()
        return total_count - read_count if total_count else 0

        

class ChatRoomSerializer(serializers.ModelSerializer):
    # 해당 채팅방에서 오간 메시지들을 포함해서 응답에 보여줌
    # read_only=True: 메시지를 API로 수정하거나 생성하진 않음
    messages = ChatMessageSerializer(many=True, read_only=True)
    content_type_info = serializers.SerializerMethodField()
    participants_profile_imgs_and_nicknames = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = (
            "id",           # 채팅방 고유 ID
            "title",        # 채팅방 제목 (예: 그룹명)
            "participants", # 채팅방 참가자들 (ManyToManyField)
            "created_at",   # 방 생성 시간
            "messages",     # 이 방의 메시지들 (역참조)
            "content_type_info",  # 연결된 모델 정보 (예: 게시글)
            "participants_profile_imgs_and_nicknames",  # 참가자들의 프로필 이미지 URL과 닉네임
        )
        # 생성 시간은 사용자가 수정할 수 없게 읽기 전용으로 설정
        read_only_fields = ("created_at",)

    def get_content_type_info(self, obj):
        """
        연결된 모델(Post 등)의 정보 반환.
        content_type과 object_id를 조합해서 어떤 모델인지 알 수 있음.
        """
        if obj.content_type:
            return {
                "id": obj.object_id,
                "title": obj.content_object.title if obj.content_object else None,
            }
        return None

    def get_participants_profile_imgs_and_nicknames(self, obj):
        """
        채팅방 참가자들의 모든 프로필 이미지 URL과 user id, 닉네임을 반환.
        """
        participants_info = []
        for participant in obj.participants.all():
            participant_info = {
                "id": participant.id,
                "nickname": participant.nickname,
                "profile_image": participant.profile_img.url if participant.profile_img else None
            }
            participants_info.append(participant_info)

        return participants_info
      