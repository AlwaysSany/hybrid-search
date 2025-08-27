import json
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from pathlib import Path
import os
from dotenv import load_dotenv


load_dotenv()

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "changeme")


def get_client_es():
    # Connect to Elasticsearch with basic auth from env
    return Elasticsearch(hosts=[ES_HOST], basic_auth=(ES_USERNAME, ES_PASSWORD))


def get_text_vector(sentences):
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(sentences)
    return embeddings


def read_json_file(file_path):
    with open(file_path, "r") as file:
        data = json.load(file)
    return data


def chunk_data(data, batch_size):
    for i in range(0, len(data), batch_size):
        yield data[i : i + batch_size]


def generate_bulk_actions(index_name, data_batch):
    for item in data_batch:
        document_id = item["id"]
        item["description_embeddings"] = get_text_vector(item["description"])
        yield {"_index": index_name, "_id": document_id, "_source": item}


def index_data_in_batches(file_path, index_name, batch_size=100):
    data = read_json_file(file_path)

    for batch in chunk_data(data, batch_size):
        actions = generate_bulk_actions(index_name, batch)
        success, failed = helpers.bulk(get_client_es(), actions)
        print(f"Batch indexed: {success} successful, {failed} failed")


if __name__ == "__main__":
    # Resolve dataset path relative to this file to avoid CWD issues
    base_dir = Path(__file__).resolve().parent
    dataset_path = (base_dir / "../files/dataset/products.json").resolve()
    index_data_in_batches(str(dataset_path), "products-catalog", batch_size=100)
