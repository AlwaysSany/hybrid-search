from elasticsearch import Elasticsearch
from fastapi import FastAPI, Query
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "changeme")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

promote_products_free_gluten = ["1043", "1042", "1039"]


def get_client_es():
    # Connect to Elasticsearch with basic auth from env
    return Elasticsearch(hosts=[ES_HOST], basic_auth=(ES_USERNAME, ES_PASSWORD))


def get_text_vector(sentences):
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(sentences)
    return embeddings


def build_query(term=None, categories=None, product_types=None, brands=None):
    must_query = (
        [{"match_all": {}}]
        if not term
        else [
            {
                "multi_match": {
                    "query": term,
                    "fields": [
                        "name^3",
                        "brand^2",
                        "category",
                        "product_type",
                        "description",
                    ],
                    "fuzziness": "AUTO",
                    "operator": "and",
                }
            }
        ]
    )

    filters = []
    if categories:
        filters.append({"terms": {"category": categories}})
    if product_types:
        filters.append({"terms": {"product_type": product_types}})
    if brands:
        filters.append({"terms": {"brand.keyword": brands}})

    query_obj = {
        "_source": [
            "id",
            "brand",
            "name",
            "price",
            "currency",
            "image_link",
            "category",
            "tag_list",
        ],
        "query": {"bool": {"must": must_query, "filter": filters}},
    }

    # Boost prefix matches on name for better UX when typing
    if term:
        shoulds = [
            {"match_phrase_prefix": {"name": {"query": term, "slop": 1, "boost": 2}}},
            {"prefix": {"brand": {"value": term.lower(), "boost": 1.2}}},
        ]
        query_obj["query"]["bool"]["should"] = shoulds
        query_obj["query"]["bool"]["minimum_should_match"] = 0

    return query_obj


def build_hybrid_query(
    term=None, categories=None, product_types=None, brands=None, hybrid=False
):
    # Standard query
    organic_query = build_query(term, categories, product_types, brands)

    if hybrid is True and term:

        vector = get_text_vector([term])[0]

        # Hybrid query with RRF (Reciprocal Rank Fusion)
        query = {
            "retriever": {
                "rrf": {
                    "retrievers": [
                        {"standard": {"query": organic_query["query"]}},
                        {
                            "knn": {
                                "field": "description_embeddings",
                                "query_vector": vector,
                                "k": 5,
                                "num_candidates": 20,
                                "filter": {"bool": {"filter": []}},
                            }
                        },
                    ],
                    "rank_window_size": 20,
                    "rank_constant": 5,
                }
            },
            "_source": organic_query["_source"],
        }

        if categories:
            query["retriever"]["rrf"]["retrievers"][1]["knn"]["filter"]["bool"][
                "filter"
            ].append({"terms": {"category": categories}})
        if product_types:
            query["retriever"]["rrf"]["retrievers"][1]["knn"]["filter"]["bool"][
                "filter"
            ].append({"terms": {"product_type": product_types}})
        if brands:
            query["retriever"]["rrf"]["retrievers"][1]["knn"]["filter"]["bool"][
                "filter"
            ].append({"terms": {"brand.keyword": brands}})
    else:
        query = organic_query

    return query


def search_products(
    term,
    categories=None,
    product_types=None,
    brands=None,
    promote_products=[],
    hybrid=False,
):
    query = build_hybrid_query(term, categories, product_types, brands, hybrid)

    if promote_products and not hybrid:
        query = {
            "query": {"pinned": {"ids": promote_products, "organic": query["query"]}},
            "_source": query["_source"],
        }

    print(query)
    # Elasticsearch v9: Avoid deprecated 'body' parameter. Pass named args instead.
    search_kwargs = {"index": "products-catalog", "size": 20}
    if "_source" in query:
        search_kwargs["_source"] = query["_source"]
    if "query" in query:
        search_kwargs["query"] = query["query"]
    if "retriever" in query:
        search_kwargs["retriever"] = query["retriever"]

    response = get_client_es().search(**search_kwargs)

    results = []
    for hit in response["hits"]["hits"]:
        print(f"Product Name: {hit['_source']['name']}, Score: {hit['_score']}")

        results.append(
            {
                "id": hit["_source"]["id"],
                "brand": hit["_source"]["brand"],
                "name": hit["_source"]["name"],
                "price": hit["_source"]["price"],
                "currency": (
                    hit["_source"]["currency"] if hit["_source"]["currency"] else "USD"
                ),
                "image_link": hit["_source"]["image_link"],
                "category": hit["_source"]["category"],
                "tags": hit["_source"].get("tag_list", []),
            }
        )

    return results


@app.get("/api/products/id/{product_id}")
def get_product_details(product_id: str):
    try:
        es = get_client_es()
        res = es.get(index="products-catalog", id=product_id)
        if not res.get("found"):
            raise HTTPException(status_code=404, detail="Product not found")
        source = res.get("_source", {})
        # Normalize response and include id
        return {
            "id": source.get("id", product_id),
            "brand": source.get("brand"),
            "name": source.get("name"),
            "price": source.get("price"),
            "currency": source.get("currency") or "USD",
            "image_link": source.get("image_link"),
            "category": source.get("category"),
            "product_type": source.get("product_type"),
            "rating": source.get("rating"),
            "description": source.get("description"),
            "tag_list": source.get("tag_list", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products/suggest")
def suggest(prefix: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)):
    """Return autocomplete suggestions for product names and brands.
    Uses prefix and fuzzy matching without requiring special index mappings.
    """
    es = get_client_es()
    should = [
        {"match_phrase_prefix": {"name": {"query": prefix, "boost": 3}}},
        {"prefix": {"name": {"value": prefix.lower(), "boost": 2}}},
        {"prefix": {"brand": {"value": prefix.lower(), "boost": 1.5}}},
        {"fuzzy": {"name": {"value": prefix, "fuzziness": "AUTO", "boost": 1}}},
    ]
    search_kwargs = {
        "index": "products-catalog",
        "size": limit,
        "_source": ["id", "name", "brand", "image_link", "price", "currency"],
        "query": {"bool": {"should": should, "minimum_should_match": 1}},
    }
    resp = es.search(**search_kwargs)
    seen = set()
    suggestions = []
    for hit in resp["hits"]["hits"]:
        source = hit.get("_source", {})
        key = source.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        suggestions.append(
            {
                "id": source.get("id"),
                "name": source.get("name"),
                "brand": source.get("brand"),
                "image_link": source.get("image_link"),
                "price": source.get("price"),
                "currency": source.get("currency") or "USD",
            }
        )
        if len(suggestions) >= limit:
            break
    return suggestions


def get_facets_data(term, categories=None, product_types=None, brands=None):
    query = build_query(term, categories, product_types, brands)
    query["aggs"] = {
        "product_types": {"terms": {"field": "product_type"}},
        "categories": {"terms": {"field": "category"}},
        "brands": {"terms": {"field": "brand.keyword"}},
    }
    # Elasticsearch v9: pass named args instead of 'body'
    search_kwargs = {"index": "products-catalog", "size": 0}
    if "_source" in query:
        search_kwargs["_source"] = query["_source"]
    if "query" in query:
        search_kwargs["query"] = query["query"]
    if "aggs" in query:
        search_kwargs["aggs"] = query["aggs"]
        search_kwargs["aggregations"] = query["aggs"]
    response = get_client_es().search(**search_kwargs)

    return {
        "product_types": [
            {"product_type": bucket["key"], "count": bucket["doc_count"]}
            for bucket in response["aggregations"]["product_types"]["buckets"]
        ],
        "categories": [
            {"category": bucket["key"], "count": bucket["doc_count"]}
            for bucket in response["aggregations"]["categories"]["buckets"]
        ],
        "brands": [
            {"brand": bucket["key"], "count": bucket["doc_count"]}
            for bucket in response["aggregations"]["brands"]["buckets"]
        ],
    }


@app.get("/api/products/search")
def search(
    query: Optional[str] = Query(None),
    selectedCategories: List[str] = Query(default=[], alias="selectedCategories[]"),
    selectedProductTypes: List[str] = Query(default=[], alias="selectedProductTypes[]"),
    selectedBrands: List[str] = Query(default=[], alias="selectedBrands[]"),
    hybrid: bool = Query(False),
):
    categories = selectedCategories
    product_types = selectedProductTypes
    brands = selectedBrands
    results = search_products(
        query,
        categories=categories,
        product_types=product_types,
        brands=brands,
        promote_products=promote_products_free_gluten,
        hybrid=hybrid,
    )
    return results


@app.get("/api/products/facets")
def facets(
    query: Optional[str] = Query(None),
    selectedCategories: List[str] = Query(default=[], alias="selectedCategories[]"),
    selectedProductTypes: List[str] = Query(default=[], alias="selectedProductTypes[]"),
    selectedBrands: List[str] = Query(default=[], alias="selectedBrands[]"),
):
    categories = selectedCategories
    product_types = selectedProductTypes
    brands = selectedBrands
    results = get_facets_data(
        query, categories=categories, product_types=product_types, brands=brands
    )
    return results


def main():
    import uvicorn
    uvicorn.run("api.api:app", host="127.0.0.1", port=5000, reload=True)


if __name__ == "__main__":
    main()
