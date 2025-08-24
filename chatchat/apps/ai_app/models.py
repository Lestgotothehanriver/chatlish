from django.db import models
from chatchat.apps.chat_app.models import ChatMessage, ChatRoom

from django.conf import settings
from django.utils import timezone
from chatchat.apps.user_app.models import User

# Create your models here.
class Description(models.Model):
    message = models.ForeignKey(ChatMessage, related_name="description", on_delete=models.CASCADE)
    context_appropriateness = models.IntegerField()
    context_appropriateness_reason = models.TextField(blank=True, null=True)
    grammer_appropriateness = models.IntegerField()
    grammer_appropriateness_reason = models.TextField(blank=True, null=True)
    vocabulary_appropriateness = models.IntegerField()
    vocabulary_appropriateness_reason = models.TextField(blank=True, null=True)

class ReferenceDescription(models.Model):
    reason_choice = (
        ("context", "Context"),
        ("grammar", "Grammar"),
        ("vocabulary", "Vocabulary"),
    )
    description = models.ForeignKey(Description, related_name="references", on_delete=models.CASCADE)
    self_id = models.IntegerField()
    reason = models.CharField(max_length=20, choices=reason_choice)

class ConversationReport(models.Model):
    """
    최종 보고서 (JSON 출력과 1:1 매핑)
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_reports",
        help_text="보고서 대상 사용자"
    )
    chat_session = models.ForeignKey(
        ChatRoom,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reports",
        help_text="보고서가 생성된 현재 채팅 세션(옵션)"
    )

    overall_summary = models.TextField(help_text="해결 접근/전략/진전 요약 (2~4문장)")
    highlights = models.TextField(help_text="특징적 시도·반복 난점·개선 포인트 (불릿 허용)")
    recommendations = models.TextField(help_text="즉시 적용 가능한 권고 (불릿 허용)")
    preview = models.CharField(max_length=160, help_text="리스트/알림용 짧은 미리보기")

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


from django.db import models
from django.utils import timezone

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    class Meta:
        indexes = [models.Index(fields=['user'])]
    summary = models.CharField(max_length=50, blank=True, default="")  # 빈 값 허용
    start_time = models.DateTimeField(default=timezone.now)
    time = models.DateTimeField()  # 최근 활동 시간

class Message(models.Model):
    SENDER_CHOICES = [
        ("user", "사용자"),
        ("model", "인공지능"),
    ]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField()
    order = models.IntegerField()

class Citation(models.Model):
    # (선택) 검색 모드일 때 인용 저장용 — 텍스트만 저장하므로 유지해도 무방
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='citations')
    text = models.TextField()
    uri = models.URLField()
