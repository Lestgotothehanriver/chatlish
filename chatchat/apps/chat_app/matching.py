# apps/chat/matching.py
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from .models import MatchTicket, MatchGroup, ChatRoom, User

QUEUE_KEY = "match:queue:{size}"
LOCK_KEY = "match:lock:{size}"
LOCK_TTL = 5  # sec
QUEUE_TTL = 3600

def _acquire_lock(key: str):
    ok = cache.add(key, "1", timeout=LOCK_TTL)
    return ok

def _release_lock(key: str):
    cache.delete(key)

def enqueue(ticket_id: int, party_size: int):
    key = QUEUE_KEY.format(size=party_size)
    client = cache.client.get_client()  # raw redis client
    client.lpush(key, ticket_id)
    client.expire(key, QUEUE_TTL)

def remove_from_queue(ticket_id: int, party_size: int):
    key = QUEUE_KEY.format(size=party_size)
    client = cache.client.get_client()
    client.lrem(key, 0, ticket_id)

def try_match(party_size: int):
    lock = LOCK_KEY.format(size=party_size)
    if not _acquire_lock(lock):
        return None, []

    try:
        client = cache.client.get_client()
        key = QUEUE_KEY.format(size=party_size)

        popped = []
        for _ in range(party_size):
            tid = client.rpop(key)
            if tid is None:
                break
            popped.append(int(tid))

        if len(popped) < party_size:
            for tid in reversed(popped):
                client.rpush(key, tid)
            return None, []

        with transaction.atomic():
            tickets_qs = MatchTicket.objects.select_for_update().filter(
                id__in=popped, status=MatchTicket.Status.WAITING
            )
            tickets = list(tickets_qs)

            if len(tickets) < party_size:
                valid_ids = {t.id for t in tickets}
                for tid in popped:
                    if tid in valid_ids:
                        client.rpush(key, tid)
                return None, []

            users = [t.user for t in tickets]
            room = ChatRoom.objects.create_room(participants=users, title="매칭 채팅방")
            group = MatchGroup.objects.create(party_size=party_size, chat_room=room)
            for t in tickets:
                t.status = MatchTicket.Status.MATCHED
                t.chat_room = room
                t.matched_at = timezone.now()
                t.save(update_fields=["status", "chat_room", "matched_at"])
                group.members.add(t.user)

            matched_ids = [t.id for t in tickets]
            return room, matched_ids
    finally:
        _release_lock(lock)
