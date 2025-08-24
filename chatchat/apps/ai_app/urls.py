# urls.py
from django.urls import path
from .views import (
    ReportCreateView,
    ChatRoomMessagesView,
    MessageDetailView,
    ChatRoomReportView,
)

urlpatterns = [
    path("report/", ReportCreateView.as_view(), name="report-create"),
    path("report/messages/", ChatRoomMessagesView.as_view(), name="report-room-messages"),
    path("report/message/<int:message_id>/", MessageDetailView.as_view(), name="report-message-detail"),
    path("report/report/", ChatRoomReportView.as_view(), name="report-room-report"),
]
