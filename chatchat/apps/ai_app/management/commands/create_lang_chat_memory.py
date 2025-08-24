from django.core.management.base import BaseCommand
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams

class Command(BaseCommand):
    help = "Create lang_chat_memory collection (non-destructive)"

    def handle(self, *args, **kwargs):
        client = QdrantClient(host="localhost", port=6333)
        cols = {c.name for c in client.get_collections().collections}
        if "lang_chat_memory" not in cols:
            client.create_collection(
                collection_name="lang_chat_memory",
                vectors_config=VectorParams(size=768, distance="Cosine")
            )
            self.stdout.write(self.style.SUCCESS("Created lang_chat_memory"))
        else:
            self.stdout.write(self.style.WARNING("lang_chat_memory already exists"))
