
import os

from dotenv import load_dotenv

load_dotenv()

INDEX = "bouncer-events"
_client = None
_index_ready = False


def get_client():
    global _client
    if _client is None:
        url, key = os.getenv("ELASTIC_URL"), os.getenv("ELASTIC_API_KEY")
        if not url or not key:
            return None
        from elasticsearch import Elasticsearch

        # Short timeout and no retries, so a slow Elastic never blocks PayPal's webhook
        _client = Elasticsearch(url, api_key=key, request_timeout=5, max_retries=0)
    return _client


def enabled():
    return get_client() is not None


def _ensure_index(client):
    global _index_ready
    if _index_ready:
        return
    if not client.indices.exists(index=INDEX):
        try:
            client.indices.create(
                index=INDEX,
                mappings={
                    "properties": {
                        "event_type": {"type": "keyword"},
                        "service": {"type": "keyword"},
                        "sub_id": {"type": "keyword"},
                        "detail": {"type": "text"},
                        "received_at": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss"},
                    }
                },
            )
        except Exception:
            pass  # another process probably created it a moment ago
    _index_ready = True


def index_event(event_id, event_type, sub_id, service, detail, received_at):
    client = get_client()
    if client is None:
        return
    _ensure_index(client)
    client.index(
        index=INDEX,
        id=event_id,  # same id = no duplicates if an event is sent twice
        document={
            "event_type": event_type,
            "service": service,
            "sub_id": sub_id,
            "detail": detail,
            "received_at": received_at,
        },
    )


def search_events(text="", event_type=None, size=25):
    client = get_client()
    _ensure_index(client)
    if text:
        must = [{"multi_match": {"query": text,
                                 "fields": ["detail", "service", "event_type"],
                                 "fuzziness": "AUTO"}}]
    else:
        must = [{"match_all": {}}]
    filters = [{"term": {"event_type": event_type}}] if event_type else []
    resp = client.search(
        index=INDEX,
        query={"bool": {"must": must, "filter": filters}},
        sort=[{"received_at": "desc"}],
        size=size,
    )
    return [hit["_source"] for hit in resp["hits"]["hits"]]


def event_counts():
    client = get_client()
    _ensure_index(client)
    resp = client.search(
        index=INDEX,
        size=0,
        aggs={"types": {"terms": {"field": "event_type", "size": 20}}},
    )
    return {b["key"]: b["doc_count"] for b in resp["aggregations"]["types"]["buckets"]}


def backfill(events, names):
    """Push events that already exist in SQLite into Elastic."""
    from elasticsearch import helpers

    client = get_client()
    _ensure_index(client)
    actions = [
        {
            "_index": INDEX,
            "_id": e["event_id"],
            "_source": {
                "event_type": e["event_type"],
                "service": names.get(e["sub_id"]),
                "sub_id": e["sub_id"],
                "detail": e["detail"],
                "received_at": e["received_at"],
            },
        }
        for e in events
    ]
    ok, _ = helpers.bulk(client, actions)
    return ok