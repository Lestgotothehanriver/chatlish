from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # admin 리스트 화면에 표시할 필드들
    list_display = ('id', 'username', 'email', 'date_joined')  
    # ↑ 여기 'id'가 user id (pk)

    # 검색창에서 검색할 필드
    search_fields = ('username', 'email')

    # 필터 사이드바
    list_filter = ('is_active', 'is_staff', 'date_joined')
