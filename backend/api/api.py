from fastapi import FastAPI, Query
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging

from .es import get_es_client
from .search import search_products, get_facets_data

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

promote_products_free_gluten = ["1043", "1042", "1039"]

 


@app.get("/api/products/id/{product_id}")
def get_product_details(product_id: str):
    try:
        es = get_es_client()
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
    es = get_es_client()
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
    uvicorn.run("backend.api.api:app", host="127.0.0.1", port=5000, reload=True)


if __name__ == "__main__":
    main()
