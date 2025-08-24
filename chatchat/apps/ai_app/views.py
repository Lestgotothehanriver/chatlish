# -*- coding: utf-8 -*-

# ======================================================================
# 공통/DRF
# ======================================================================
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError

# ======================================================================
# 프로젝트 모델 및 시리얼라이저 (첫 번째 파일)
# ======================================================================
from chatchat.apps.user_app.models import User
from .models import ChatSession, Message, Citation
from .serializers import ChatSerializer, MessageSerializer

# ======================================================================
# 프로젝트 모델 및 시리얼라이저 (두 번째 파일)
# ======================================================================
from chatchat.apps.chat_app.models import ChatMessage, ChatRoom
from .models import Description, ConversationReport, ReferenceDescription
from .serializers import (
    ChatMessageListItemSerializer,
    ChatMessageDetailSerializer,
    ConversationReportSerializer,
)

# ======================================================================
# 외부 라이브러리
# ======================================================================
import os
import threading
import json
import uuid
import re
import mimetypes
from distutils.util import strtobool

import numpy
from numpy.linalg import norm

from dotenv import load_dotenv

import google.generativeai as generativeai
from google.genai import types
from google import genai
from google.genai.types import Part, Content

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# ======================================================================
# 환경 설정 / 클라이언트
# ======================================================================
load_dotenv()
generativeai.configure(api_key=os.environ["GEMINI_API_KEY"])
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ======================================================================
# (첫 번째 파일) system prompts
# ======================================================================
user_context_prompt = """유저의 메시지를 읽고, 다음 두 가지를 판단해, 경우에 따라 문자열 “True” 또는 “False”를 출력해 주세요.
해당 메시지가 데이터베이스에서 유저의 성향, 취향, 관심사, 개인적인 정보 등 추가적인 사용자의 정보를 검색해 와야 한다면 True, 아닌 경우에는 False를 출력해 주세요. 
Ex:
“지금까지의 대화 내용을 바탕으로 내 성향을 분석해줘” > “True”
“내가 그때 이야기했던 친구 기억나?” > “True”
“트랜스포머에 대해서 알려줘” > “False”
“케이팝 데몬 헌터스에 대해 검색해서 알려줘” > “False”
주의사항: 당신은 반드시 "True", 혹은 "False"만 출력해야 하고, 그 이외의 출력은 허용하지 않습니다."""

search_prompt = """유저의 메시지를 읽고, 다음 두 가지를 판단해, 경우에 따라 문자열 “True” 또는 “False”를 출력해 주세요.
해당 메시지가 최신 정보를 검색해 와야 한다면 True, 아닌 경우에는 False를 출력해 주세요.
Ex:
"케데헌에 대해 알려줘" > "True"
"미적분학에 대해서 알려줘" > "False"
주의사항: 당신은 반드시 "True", 혹은 "False"만 출력해야 하고, 그 이외의 출력은 허용하지 않습니다."""

embed_prompt = """당신은 언어 모델의 개인화된 답변을 제공하기 위해, 사용자 맞춤 메모리 데이터베이스를 구축하는 AI입니다. 
당신의 역할은, 유저가 입력한 메세지를 읽고, 해당 메시지가 데이터베이스에 저장할 만한 가치가 있는지 판단하는 것입니다.
당신이 출력해야 할 문자열은 “True”와 “False”입니다.
유저의 성향, 취향, 관심사, 개인 정보등을 나타내는 정보가 포함되어 있다면, 해당 메시지를 데이터베이스에 저장할 만한 가치가 있다고 판단하고, “True”를 출력하세요.
아니라면, “False”를 출력하세요.
출력 예시: 
나 요즘에 좋아하는 애가 있어. 그 아이 이름은 지우야. > True
오늘 점심 짜장면 먹을까 짬뽕 먹을까? > False
주의사항: 당신은 반드시 "True", 혹은 "False"만 출력해야 하고, 그 이외의 출력은 허용하지 않습니다."""

# ======================================================================
# (두 번째 파일) JSON 스키마 및 프롬프트
# ======================================================================
EVAL_SCHEMA = {
    "type": "OBJECT",
    "required": [
        "context_appropriateness",
        "context_appropriateness_reason",
        "grammer_appropriateness",
        "grammer_appropriateness_reason",
        "vocabulary_appropriateness",
        "vocabulary_appropriateness_reason",
    ],
    "properties": {
        "context_appropriateness": {"type": "INTEGER"},
        "context_appropriateness_reason": {"type": "STRING"},
        "grammer_appropriateness": {"type": "INTEGER"},
        "grammer_appropriateness_reason": {"type": "STRING"},
        "vocabulary_appropriateness": {"type": "INTEGER"},
        "vocabulary_appropriateness_reason": {"type": "STRING"},
    },
}

REPORT_SCHEMA = {
    "type": "OBJECT",
    "required": ["overall_summary", "highlights", "recommendations", "preview"],
    "properties": {
        "overall_summary": {"type": "STRING"},
        "highlights": {"type": "STRING"},
        "recommendations": {"type": "STRING"},
        "preview": {"type": "STRING"},
    },
}

# 주의: 이 이름은 두 번째 파일이 사용하던 글로벌 이름을 그대로 둡니다.
system_prompt = """You are an evaluator. Given a conversation string where each line is in the format 'nickname: (real nickname value here), message: (real message here)', evaluate ONLY the last user's message. 
Return ONLY a JSON object with the exact keys shown below. Do not add extra text or keys.

Criteria & Guidelines

Context Appropriateness
5: Fully appropriate, natural, and coherent for the given context/purpose.
4: Mostly appropriate; only minor contextual awkwardness.
3: Partly appropriate; noticeable awkwardness or slight mismatch.
2: Largely inappropriate or confusing for the context.
1: Irrelevant, nonsensical, or clearly off-context.

Grammar Appropriateness
5: No grammatical errors.
4: Minor errors that don’t hinder comprehension.
3: Several errors that slightly reduce fluency but remain understandable.
2: Frequent/serious errors that impair clarity.
1: Severely ungrammatical and hard to understand.

Vocabulary Appropriateness
5: Precise, varied, idiomatic word choice that fits the context.
4: Good choices with minor issues (slight repetition or less natural word).
3: Basic or somewhat awkward/imprecise choices.
2: Poor/unnatural choices; noticeable misuse.
1: Very poor, incorrect, or nonsensical vocabulary.

Output Requirements
Return only JSON (no code fences, no prose).

Keys (must match exactly):
context_appropriateness (integer 1–5)
context_appropriateness_reason (≤2 sentences, concise, MUST be in Korean)
grammer_appropriateness (integer 1–5) ← (use this exact spelling)
grammer_appropriateness_reason (≤2 sentences, concise, MUST be in Korean)
vocabulary_appropriateness (integer 1–5)
vocabulary_appropriateness_reason (≤2 sentences, concise, MUST be in Korean)

Reasons must be short and concrete (max two sentences each).
Do not include the original sentence or scores outside the JSON.

Return JSON exactly in this structure
{
"context_appropriateness": <1-5>,
"context_appropriateness_reason": "<max two concise sentences in Korean>",
"grammer_appropriateness": <1-5>,
"grammer_appropriateness_reason": "<max two concise sentences in Korean>",
"vocabulary_appropriateness": <1-5>,
"vocabulary_appropriateness_reason": "<max two concise sentences in Korean>"
}
"""

report_prompt = """
You are a professional English-learning progress reporter.
You will receive two inputs:
1) target_nickname: 보고서를 생성해야 할 특정 유저의 닉네임
2) conversation: a conversation string composed of lines in the exact format "nickname: (real nickname here), message: (real message here)". This is the full current chat session (ALL users' messages).

Task:
Analyze ONLY the messages where nickname == target_nickname.  
Focus on how the user tried to understand or solve problems, what strategies they used, and what progress or difficulties were visible.  
Do not focus on micro-level grammar/vocab scoring.

All output MUST be valid JSON object that directly matches the ConversationReport model fields.  
Keys must exactly match: ["overall_summary", "highlights", "recommendations", "preview"].  
Do not include any other keys or explanations.  
All values must be Korean text (preview ≤ 160 chars).  

Example output:
{
  "overall_summary": "사용자는 문제 해결을 위해 다양한 시도를 했으며...",
  "highlights": "- 반복된 오류를 스스로 인식함\n- 어휘 활용이 점차 개선됨",
  "recommendations": "- 문장 연결 표현을 집중 연습\n- 자주 틀린 패턴을 별도로 정리\n- 실생활 예시를 활용해 반복 학습",
  "preview": "반복 오류를 인식하고 개선하려는 태도가 뚜렷함"
}
"""

# ======================================================================
# 유틸 (공통)
# ======================================================================
def to_bool(val):
    if val in (True, False, None):
        return val
    try:
        return bool(strtobool(str(val).strip()))
    except ValueError:
        return None


def get_embedding(text: str, is_query: bool) -> list[float]:
    task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=768),
    )
    [embedding_obj] = response.embeddings
    embedding_values_np = numpy.array(embedding_obj.values)
    normed_embedding = embedding_values_np / norm(embedding_values_np)
    return normed_embedding.tolist()

# ======================================================================
# (첫 번째 파일) 벡터화/판단 함수
# ======================================================================
def vectorize_and_store(message: Message):
    vector = get_embedding(message.message, is_query=False)
    qdrant = QdrantClient(host="localhost", port=6333)
    qdrant.upsert(
        collection_name="chat_memory",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": message.message,
                    "user_id": message.session.user.id,
                    "session_id": message.session.id,
                },
            )
        ],
    )


def is_embed_node(message: Message, embed_prompt: str, user_input: str, client: genai.Client) -> bool:
    cfg = types.GenerateContentConfig(system_instruction=embed_prompt)
    parts = [Part(text=user_input)]
    res = client.models.generate_content(
        model="gemini-2.5-flash",
        config=cfg,
        contents=[Content(role="user", parts=parts)],
    )
    return res.text == "True"


def embed_task(message: Message, embed_prompt: str, user_input: str, client: genai.Client):
    if is_embed_node(message, embed_prompt, user_input, client):
        vectorize_and_store(message)


def is_user_context_required(user_input: str, client: genai.Client) -> bool:
    cfg = types.GenerateContentConfig(system_instruction=user_context_prompt)
    parts = [Part(text=user_input)]
    res = client.models.generate_content(
        model="gemini-2.5-flash",
        config=cfg,
        contents=[Content(role="user", parts=parts)],
    )
    return res.text == "True"


def user_context_node(query_text: str, user_id: int):
    qdrant = QdrantClient(host="localhost", port=6333)
    return qdrant.search(
        collection_name="chat_memory",
        query_vector=get_embedding(query_text, is_query=True),
        limit=20,
        query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
    )


def is_search_required(user_input: str, client: genai.Client) -> bool:
    cfg = types.GenerateContentConfig(system_instruction=search_prompt)
    parts = [Part(text=user_input)]
    res = client.models.generate_content(
        model="gemini-2.5-flash",
        config=cfg,
        contents=[Content(role="user", parts=parts)],
    )
    return res.text == "True"

# ======================================================================
# (두 번째 파일) 랭귀지 평가/검색 유틸
# ======================================================================
def reason_to_string(reason: int) -> str:
    if reason == 1:
        return "context"
    elif reason == 2:
        return "grammar"
    elif reason == 3:
        return "vocabulary"
    else:
        raise ValueError("Invalid reason value. Must be 1, 2, or 3.")


def lang_vectorize_and_store(message: ChatMessage, reasons: list[int]) -> None:
    vector = get_embedding(message.text, is_query=False)
    client_q = QdrantClient(host="localhost", port=6333)
    client_q.upsert(
        collection_name="lang_chat_memory",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": message.text,
                    "user_id": message.sender.id,
                    "room_id": message.room.id,
                    "reasons": reasons,
                },
            )
        ],
    )


def lang_user_context_node(query_text: str, user_id: int, limit: int, reason: int) -> list:
    client_q = QdrantClient(host="localhost", port=6333)
    search_result = client_q.search(
        collection_name="lang_chat_memory",
        query_vector=get_embedding(query_text, is_query=True),
        limit=limit,
        query_filter={
            "must": [
                {"key": "user_id", "match": {"value": user_id}},
                {"key": "reasons", "match": {"any": [reason]}},
            ]
        },
    )
    return search_result

# ======================================================================
# (첫 번째 파일) API Views — 채팅 세션
# ======================================================================
class ChatView(APIView):
    """유저의 모든 챗 세션을 조회"""

    def get(self, request, user_id):
        if not user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, id=user_id)
        sessions = user.chatsession_set.all().order_by('-time')
        serializer = ChatSerializer(sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChatSessionGetView(APIView):
    """특정 챗 세션의 메시지 조회/삭제"""

    def get(self, request, session_id):
        if not session_id:
            return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(ChatSession, id=session_id)
        messages = session.message_set.all().order_by('order')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, session_id):
        if not session_id:
            return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = ChatSession.objects.get(id=session_id)
            session.delete()
            return Response({'message': 'Session deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except ChatSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)


class ChatSessionPostView(APIView):
    """새 세션 생성 또는 기존 세션에 메시지 추가 (텍스트만)"""
    parser_classes = (JSONParser,)

    def post(self, request):
        # 입력 파라미터
        session_id = request.data.get('session_id')
        user_input = request.data.get('user_input')
        is_search = to_bool(request.data.get('is_search', False))

        # 세션 생성 또는 로드
        if not session_id:
            session = ChatSession.objects.create(
                user_id=request.data.get('user_id'),
                time=timezone.now(),
                start_time=timezone.now(),
            )
            session_id = session.id
            history = []
            order = 0
        else:
            session = get_object_or_404(ChatSession, id=session_id)
            session.time = timezone.now()
            qs = session.message_set.all().order_by('order')
            last = qs.last()
            order = (last.order + 1) if last else 0
            history = []
            for m in qs:
                history.append(Content(role=m.sender.lower(), parts=[Part(text=m.message)]))

        if not user_input:
            return Response({'error': 'user_input is required'}, status=status.HTTP_400_BAD_REQUEST)

        # 로컬(system_prompt) — 두 번째 파일의 글로벌 system_prompt와 이름이 같아도
        # 여기서는 함수 내부 로컬 변수이므로 동작에 영향 없음
        system_prompt_local = "You are a helpful, concise assistant. Reply in the user's language."

        # 사용자 컨텍스트 필요 시 벡터 검색
        if is_user_context_required(user_input, client):
            search_result = user_context_node(user_input, session.user.id)
            if search_result:
                user_context = " ".join([point.payload.get('text', '') for point in search_result])
                system_prompt_local += f"\n\nUser prior context (use if helpful): {user_context}"

        # 최신 정보 검색 필요 여부
        is_search = is_search or is_search_required(user_input, client)

        # 생성 설정
        if is_search:
            grounding_tool = types.Tool(google_search=types.GoogleSearch())
            gen_config = types.GenerateContentConfig(
                tools=[grounding_tool],
                system_instruction=system_prompt_local,
            )
        else:
            gen_config = types.GenerateContentConfig(system_instruction=system_prompt_local)

        # 모델 호출
        try:
            parts = [Part(text=user_input)]
            history.append(Content(role="user", parts=parts))
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=history,
                config=gen_config,
            )
            model_output = response.text or ""

            # 검색 인용 수집(있으면)
            search_result_pairs = []
            if is_search:
                citations = []
                titles = []
                cand0 = response.candidates[0] if getattr(response, "candidates", None) else None
                gmeta = getattr(cand0, "grounding_metadata", None) if cand0 else None
                chunks = getattr(gmeta, "grounding_chunks", None) if gmeta else None
                if chunks:
                    for ch in chunks:
                        if getattr(ch, "web", None) and getattr(ch.web, "uri", None):
                            citations.append(ch.web.uri)
                            titles.append(getattr(ch.web, "title", ch.web.uri))
                search_result_pairs = list(zip(citations, titles))

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 메시지 저장
        user_msg = Message.objects.create(
            session=session,
            sender='user',
            message=user_input,
            order=order,
        )
        model_msg = Message.objects.create(
            session=session,
            sender='model',
            message=model_output,
            order=order + 1,
        )

        # 인용 저장(선택)
        if is_search and search_result_pairs:
            for (uri, title) in search_result_pairs:
                Citation.objects.create(message=model_msg, text=title, uri=uri)

        # 첫 교환이면 세션 요약 생성
        if order == 0:
            user_obj = session.user
            country = user_obj.country.name if getattr(user_obj, "country", None) else "Unknown"
            sp = (
                "Summarize the following conversation in one short sentence (less than 5 words) "
                "that clearly conveys the user's main intent or request. "
                f"Be specific and avoid vague summaries. The user is from {country}. "
                "Use the user's language."
            )
            cfg = types.GenerateContentConfig(system_instruction=sp)
            summary_res = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[Content(parts=[Part(text=model_output)])],
                config=cfg,
            )
            session.summary = (summary_res.text or "")[:50]
            session.save()

        # 백그라운드 벡터화(텍스트만)
        threading.Thread(
            target=embed_task, args=(user_msg, embed_prompt, user_input, client), daemon=True
        ).start()

        # 응답
        return Response(
            {
                'response': [model_output],      # 항상 리스트 형태로 반환(프론트 호환)
                'session_id': session_id,
                'search_result': search_result_pairs,  # [(uri, title), ...]
            },
            status=status.HTTP_200_OK,
        )

# ======================================================================
# (두 번째 파일) API Views — 리포트 생성/조회
# ======================================================================
class ReportCreateView(APIView):

    def post(self, request):
        """
        Role: 사용자들의 채팅 메시지를 검토하고, 이에 대한 평가를 생성하는 API 뷰
        URL: /api/ai/report/
        Input: Post 요청으로 request body에 "room_id"와 "user_id"를 포함
        return: 모델의 응답을 반환
        """
        room_id = request.data.get("room_id")
        room = get_object_or_404(ChatRoom, id=room_id)
        user_id = int(request.data.get("user_id"))
        context = ""
        messages = room.messages.all().order_by("created_at")

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,  # 두 번째 파일의 글로벌 이름 유지
            response_schema=EVAL_SCHEMA,
            response_mime_type="application/json",
        )
        report_config = types.GenerateContentConfig(
            system_instruction=report_prompt,
            response_schema=REPORT_SCHEMA,
            response_mime_type="application/json",
        )

        for m in messages:
            if m.sender.id != user_id:
                context += f"{m.sender.username}: {m.text}\n"
                continue

            context += f"{m.sender.username}: {m.text}\n"
            parts = [Part(text=context)]
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[Content(parts=parts)],
                config=config,
            )

            response_json = json.loads(response.text)
            context_appropriateness = int(response_json["context_appropriateness"])
            grammer_appropriateness = int(response_json["grammer_appropriateness"])
            vocabulary_appropriateness = int(response_json["vocabulary_appropriateness"])

            description = Description.objects.create(
                message=m,
                context_appropriateness=context_appropriateness,
                context_appropriateness_reason=response_json["context_appropriateness_reason"],
                grammer_appropriateness=grammer_appropriateness,
                grammer_appropriateness_reason=response_json["grammer_appropriateness_reason"],
                vocabulary_appropriateness=vocabulary_appropriateness,
                vocabulary_appropriateness_reason=response_json["vocabulary_appropriateness_reason"],
            )

            # 기준 미달 항목별로 과거 유사 오류 참조 & 벡터화 사유 기록
            reasons = []
            if context_appropriateness < 3:
                reason = 1
                reasons.append(reason)
                search_results = lang_user_context_node(
                    query_text=m.text, user_id=m.sender.id, reason=reason, limit=1
                )
                if search_results:
                    reason_str = reason_to_string(reason)
                    for result in search_results:
                        ReferenceDescription.objects.create(
                            description=description,
                            self_id=result.id,
                            reason=reason_str,
                        )

            if grammer_appropriateness < 3:
                reason = 2
                reasons.append(reason)
                search_results = lang_user_context_node(
                    query_text=m.text, user_id=m.sender.id, reason=reason, limit=1
                )
                if search_results:
                    reason_str = reason_to_string(reason)
                    for result in search_results:
                        ReferenceDescription.objects.create(
                            description=description,
                            self_id=result.id,
                            reason=reason_str,
                        )

            if vocabulary_appropriateness < 3:
                reason = 3
                reasons.append(reason)
                search_results = lang_user_context_node(
                    query_text=m.text, user_id=m.sender.id, reason=reason, limit=1
                )
                if search_results:
                    reason_str = reason_to_string(reason)
                    for result in search_results:
                        ReferenceDescription.objects.create(
                            description=description,
                            self_id=result.id,
                            reason=reason_str,
                        )

            # 벡터화 및 저장
            lang_vectorize_and_store(m, reasons)

        # 최종 보고서 생성
        # (username 변수는 기존 코드의 흐름을 존중하여 유지 — 필요 시 사용)
        username = User.objects.get(id=user_id).username  # noqa: F841

        report_str = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[Content(parts=[Part(text=context)])],
            config=report_config,
        )
        report_json = json.loads(report_str.text)

        report = ConversationReport.objects.create(
            user=User.objects.get(id=user_id),
            chat_session=room,
            overall_summary=report_json["overall_summary"],
            highlights=report_json["highlights"],
            recommendations=report_json["recommendations"],
            preview=report_json["preview"],
        )

        return Response(
            {"message": "Report created successfully", "report_id": report.id},
            status=status.HTTP_201_CREATED,
        )

# ======================================================================
# (두 번째 파일) 조회용 API (메시지/리포트)
# ======================================================================
class ChatRoomMessagesView(ListAPIView):
    """
    특정 ChatRoom의 모든 메시지 내역 (점수 요약 포함)
    GET /api/ai/report/messages/?room_id=123
    """
    permission_classes = [AllowAny]
    serializer_class = ChatMessageListItemSerializer

    def get_queryset(self):
        room_id = self.request.query_params.get("room_id")
        if not room_id:
            raise ValidationError({"room_id": "This query param is required."})

        room = get_object_or_404(ChatRoom, id=room_id)
        qs = (
            room.messages
            .select_related("sender")                          # 정방향 FK만 select_related
            .prefetch_related("description", "description__references")  # 역방향은 prefetch
            .order_by("created_at")
        )
        return qs


class MessageDetailView(RetrieveAPIView):
    """
    특정 메시지 상세 (점수/이유/모든 references)
    GET /api/ai/report/message/<message_id>/
    """
    permission_classes = [AllowAny]
    serializer_class = ChatMessageDetailSerializer
    lookup_url_kwarg = "message_id"
    lookup_field = "id"

    def get_queryset(self):
        return (
        ChatMessage.objects
        .select_related("sender")
        .prefetch_related("description", "description__references")  # ✅
    )

class ChatRoomReportView(APIView):
    """
    특정 ChatRoom의 최신 Report 조회 (옵션: user_id로 필터)
    - GET /api/ai/report/report/?room_id=123            -> 해당 방의 최신 보고서 1건
    - GET /api/ai/report/report/?room_id=123&user_id=7  -> 해당 유저의 최신 보고서 1건
    """
    permission_classes = [AllowAny]

    def get(self, request):
        room_id = request.query_params.get("room_id")
        user_id = request.query_params.get("user_id")

        if not room_id:
            return Response({"detail": "room_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        room = get_object_or_404(ChatRoom, id=room_id)

        reports = ConversationReport.objects.filter(chat_session=room)
        if user_id:
            reports = reports.filter(user_id=user_id)

        report = reports.order_by("-created_at").select_related("user").first()
        if not report:
            return Response({"detail": "No report found for given criteria."}, status=status.HTTP_404_NOT_FOUND)

        data = ConversationReportSerializer(report).data
        return Response(data, status=status.HTTP_200_OK)
