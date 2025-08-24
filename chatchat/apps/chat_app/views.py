from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ChatRoom, ChatMessage, Image, UserDeviceToken
from .serializers import ChatRoomListSerializer, ChatRoomSerializer, ChatMessageSerializer
from rest_framework.views import APIView

class ChatRoomViewSet(viewsets.ModelViewSet):
    """
    채팅방을 조회, 생성, 삭제, 수정할 수 있는 API를 자동으로 만들어주는 클래스.
    예: /chatrooms/ → 방 목록, /chatrooms/1/ → 방 상세, 등
    """

    queryset = ChatRoom.objects.all()  # 기본적으로 전체 방을 가져오지만 아래 get_queryset에서 필터링함
    permission_classes = [permissions.IsAuthenticated]  # 로그인한 사람만 접근 가능
    serializer_class = ChatRoomSerializer  # 기본 직렬화 클래스

    def get_serializer_class(self):
        if self.action == "list":
            return ChatRoomListSerializer

        elif self.action == "retrieve":
            return ChatRoomSerializer

        return self.serializer_class  

    def paginate_queryset(self, queryset):
        if self.action == 'list':  # list일 때만 페이지네이션 끄기
            return None
        return super().paginate_queryset(queryset)

    def get_queryset(self):
        """
        오버라이딩: 전체 방이 아닌,
        현재 로그인한 유저가 '참여자'로 들어있는 방만 필터링해서 보여줌.
        GET 요청 시 자동으로 호출됨. 
        GET: /api/chatrooms/
        GET: /api/chatrooms/3
        """
        return ChatRoom.objects.filter(participants=self.request.user)

    def perform_create(self, serializer):
        """
        채팅방 생성할 때 호출됨.
        방을 만들면서 자동으로 만든 사람을 참여자에 추가함.
        POST 요청 시 자동으로 호출됨
        POST: /api/chatrooms/
        """
        room = serializer.save()  # 방 저장
        room.participants.add(self.request.user)  # 본인을 참여자에 추가

    @action(detail=True, methods=["patch"])
    def out(self, request, pk=None):
        """
        PATCH /chatrooms/<pk>/out/
        현재 유저를 채팅방 참여자 목록에서 제거함.
        """
        room = self.get_object()
        user = request.user

        room.participants.remove(user)

        if room.content_object._meta.model_name == "carpoolpost":
            if room.content_object.author == user:
                # 카풀 게시글의 작성자가 나가는 경우
                room.content_object.delete()
            else:
                # 카풀 게시글의 참가자가 나가는 경우
                room.content_object.passengers.remove(user) 
        elif room.content_object._meta.model_name == "connectionpost":
            if room.content_object.author == user:
                # 커넥션 게시글의 작성자가 나가는 경우
                room.content_object.delete()
            else:
                # 커넥션 게시글의 참가자가 나가는 경우
                room.content_object.members.remove(user) 
        return Response({"message": "채팅방에서 나갔습니다."}, status=status.HTTP_200_OK)

class ImageUploadView(APIView):
    """
    채팅방 메시지에 첨부할 이미지를 업로드하는 API.
    POST 요청으로 이미지 파일을 받음.
    """

    permission_classes = [permissions.IsAuthenticated]  # 로그인한 사람만 접근 가능

    def post(self, request):
        """
        POST /api/chat/upload/
        이미지 파일을 받아서 저장하고 URL 반환
        """
        if 'images' not in request.FILES:
            return Response({"error": "이미지 파일이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        images = request.FILES.getlist('images')
        img_ids = []
        for image in images:
            img = Image.objects.create(image=image)
            img_ids.append(img.id)
        
        return Response({"image_ids": img_ids}, status=status.HTTP_201_CREATED)




        
        
