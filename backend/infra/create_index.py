from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

index_name = "products-catalog"
mapping = {
    "settings": {
        "index": {
            "number_of_replicas": 0,
            "number_of_shards": 1,
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "brand": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "name": {"type": "text"},
            "price": {"type": "float"},
            "price_sign": {"type": "keyword"},
            "currency": {"type": "keyword"},
            "image_link": {"type": "keyword"},
            "description": {"type": "text"},
            # Enable vector indexing for kNN search in ES 8+/9+
            "description_embeddings": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine",
            },
            "rating": {"type": "keyword"},
            "category": {"type": "keyword"},
            "product_type": {"type": "keyword"},
            "tag_list": {"type": "keyword"},
        }
    },
}

load_dotenv()

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "changeme")


def get_client_es():
    # Connect to Elasticsearch with basic auth from env
    return Elasticsearch(hosts=[ES_HOST], basic_auth=(ES_USERNAME, ES_PASSWORD))


def create_index(index_name, mapping):
    es = get_client_es()
    if not es.indices.exists(index=index_name):
        es.indices.create(
            index=index_name,
            settings=mapping.get("settings"),
            mappings=mapping.get("mappings"),
        )
        print(f"Index '{index_name}' created successfully.")
    else:
        print(f"Index '{index_name}' already exists.")


create_index(index_name, mapping)
