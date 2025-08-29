from typing import List, Optional
import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from .es import get_es_client


@lru_cache(maxsize=1)
def _get_model():
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def get_text_vector(sentences: List[str]):
    model = _get_model()
    return model.encode(sentences)


def build_query(term: Optional[str] = None,
                categories: Optional[List[str]] = None,
                product_types: Optional[List[str]] = None,
                brands: Optional[List[str]] = None):
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

    if term:
        shoulds = [
            {"match_phrase_prefix": {"name": {"query": term, "slop": 1, "boost": 2}}},
            {"prefix": {"brand": {"value": term.lower(), "boost": 1.2}}},
        ]
        query_obj["query"]["bool"]["should"] = shoulds
        query_obj["query"]["bool"]["minimum_should_match"] = 0

    return query_obj


def build_hybrid_query(term: Optional[str] = None,
                        categories: Optional[List[str]] = None,
                        product_types: Optional[List[str]] = None,
                        brands: Optional[List[str]] = None,
                        hybrid: bool = False):
    organic_query = build_query(term, categories, product_types, brands)

    if hybrid is True and term:
        vector = get_text_vector([term])[0]
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

    logging.info(query)
    return query


def search_products(term: Optional[str],
                    categories: Optional[List[str]] = None,
                    product_types: Optional[List[str]] = None,
                    brands: Optional[List[str]] = None,
                    promote_products: Optional[List[str]] = None,
                    hybrid: bool = False):
    query = build_hybrid_query(term, categories, product_types, brands, hybrid)

    if promote_products and not hybrid:
        query = {
            "query": {"pinned": {"ids": promote_products, "organic": query["query"]}},
            "_source": query["_source"],
        }

    logging.info(query)
    search_kwargs = {"index": "products-catalog", "size": 20}
    if "_source" in query:
        search_kwargs["_source"] = query["_source"]
    if "query" in query:
        search_kwargs["query"] = query["query"]
    if "retriever" in query:
        search_kwargs["retriever"] = query["retriever"]

    es = get_es_client()
    response = es.search(**search_kwargs)

    results = []
    for hit in response["hits"]["hits"]:
        logging.info(f"Product Name: {hit['_source']['name']}, Score: {hit['_score']}")
        results.append(
            {
                "id": hit["_source"]["id"],
                "brand": hit["_source"]["brand"],
                "name": hit["_source"]["name"],
                "price": hit["_source"]["price"],
                "currency": (hit["_source"].get("currency") or "USD"),
                "image_link": hit["_source"]["image_link"],
                "category": hit["_source"]["category"],
                "tags": hit["_source"].get("tag_list", []),
            }
        )

    return results


def get_facets_data(term: Optional[str],
                    categories: Optional[List[str]] = None,
                    product_types: Optional[List[str]] = None,
                    brands: Optional[List[str]] = None):
    query = build_query(term, categories, product_types, brands)
    query["aggs"] = {
        "product_types": {"terms": {"field": "product_type"}},
        "categories": {"terms": {"field": "category"}},
        "brands": {"terms": {"field": "brand.keyword"}},
    }

    search_kwargs = {"index": "products-catalog", "size": 0}
    if "_source" in query:
        search_kwargs["_source"] = query["_source"]
    if "query" in query:
        search_kwargs["query"] = query["query"]
    if "aggs" in query:
        search_kwargs["aggs"] = query["aggs"]
        search_kwargs["aggregations"] = query["aggs"]

    es = get_es_client()
    response = es.search(**search_kwargs)

    return {
        "product_types": [
            {"product_type": b["key"], "count": b["doc_count"]}
            for b in response["aggregations"]["product_types"]["buckets"]
        ],
        "categories": [
            {"category": b["key"], "count": b["doc_count"]}
            for b in response["aggregations"]["categories"]["buckets"]
        ],
        "brands": [
            {"brand": b["key"], "count": b["doc_count"]}
            for b in response["aggregations"]["brands"]["buckets"]
        ],
    }
