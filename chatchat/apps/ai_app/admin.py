from django.contrib import admin

# Register your models here.
from .models import (
    Description,
    ReferenceDescription,
    ConversationReport,
)
admin.site.register(Description)
admin.site.register(ReferenceDescription)
admin.site.register(ConversationReport)
