import os
from functools import lru_cache
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "changeme")


@lru_cache(maxsize=1)
def get_es_client() -> Elasticsearch:
    """Return a cached Elasticsearch client using env configuration.
    Uses basic auth and supports a single host URL from ES_HOST.
    """
    return Elasticsearch(hosts=[ES_HOST], basic_auth=(ES_USERNAME, ES_PASSWORD))
