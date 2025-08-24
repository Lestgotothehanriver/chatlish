
# serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers

from chatchat.apps.chat_app.models import ChatMessage, ChatRoom
from .models import Description, ReferenceDescription, ConversationReport, ChatSession
from .models import ChatSession, Message
User = get_user_model()

class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ('id', 'user', 'summary', 'start_time', 'time')

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ('id', 'session', 'sender', 'message', 'order')

class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")


class ReferenceDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceDescription
        fields = ("id", "self_id", "reason")


class DescriptionBriefSerializer(serializers.ModelSerializer):
    references_count = serializers.SerializerMethodField()

    class Meta:
        model = Description
        fields = (
            "context_appropriateness",
            "grammer_appropriateness",
            "vocabulary_appropriateness",
            "references_count",
        )

    def get_references_count(self, obj):
        return obj.references.count()


class DescriptionDetailSerializer(serializers.ModelSerializer):
    references = ReferenceDescriptionSerializer(many=True, read_only=True)

    class Meta:
        model = Description
        fields = (
            "id",
            "context_appropriateness",
            "context_appropriateness_reason",
            "grammer_appropriateness",
            "grammer_appropriateness_reason",
            "vocabulary_appropriateness",
            "vocabulary_appropriateness_reason",
            "references",
        )


class ChatMessageListItemSerializer(serializers.ModelSerializer):
    sender = UserMiniSerializer(read_only=True)
    description = DescriptionBriefSerializer(source="description.all", many=True, read_only=True)  # ✅

    class Meta:
        model = ChatMessage
        fields = ("id", "text", "created_at", "sender", "description")

class ChatMessageDetailSerializer(serializers.ModelSerializer):
    sender = UserMiniSerializer(read_only=True)
    # 디테일용: 이유/레퍼런스까지 풀셋
    description = DescriptionBriefSerializer(source="description.all", many=True, read_only=True)

    class Meta:
        model = ChatMessage
        fields = ("id", "text", "sender", "created_at", "description")

class ConversationReportSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = ConversationReport
        fields = (
            "id",
            "user",
            "chat_session",
            "overall_summary",
            "highlights",
            "recommendations",
            "preview",
            "created_at",
        )
