import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  createTracker,
  trackPageView,
  trackSearch,
  trackSearchClick
} from "@elastic/behavioral-analytics-javascript-tracker";

createTracker({
  endpoint: "endpoint",
  collectionName: "tracking-search",
  apiKey: "key"
});

const Facets = ({ categories = [], productTypes = [], brands = [], selectedFacets, onFacetChange }) => {
  return (
    <div className="facets">
      <h3 className="facets-title">Filters</h3>

      <h4>Categories</h4>
      {categories.map((facet, index) => (
        <div key={`category-${index}`} className="facet-item">
          <input
            type="checkbox"
            checked={selectedFacets.categories.includes(facet.category)}
            onChange={() => onFacetChange('categories', facet.category)}
          />
          <label>{facet.category || "Others"} ({facet.count})</label>
        </div>
      ))}

      <h4>Brands</h4>
      {brands.map((facet, index) => (
        <div key={`category-${index}`} className="facet-item">
          <input
            type="checkbox"
            checked={selectedFacets.brands.includes(facet.brand)}
            onChange={() => onFacetChange('brands', facet.brand)}
          />
          <label>{facet.brand || "Others"} ({facet.count})</label>
        </div>
      ))}

      <h4>Types</h4>
      {productTypes.map((facet, index) => (
        <div key={`product-type-${index}`} className="facet-item">
          <input
            type="checkbox"
            checked={selectedFacets.productTypes.includes(facet.product_type)}
            onChange={() => onFacetChange('productTypes', facet.product_type)}
          />
          <label>{facet.product_type} ({facet.count})</label>
        </div>
      ))}
    </div>
  );
};

const SearchBar = ({ searchQuery, setSearchQuery, onSearch }) => {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggest, setShowSuggest] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    let timer;
    const q = searchQuery?.trim();
    if (q && q.length >= 1) {
      timer = setTimeout(async () => {
        try {
          const res = await axios.get('http://127.0.0.1:5000/api/products/suggest', {
            params: { prefix: q, limit: 8 }
          });
          setSuggestions(res.data || []);
          setShowSuggest(true);
          setActiveIndex(-1);
        } catch (e) {
          setSuggestions([]);
        }
      }, 180);
    } else {
      setSuggestions([]);
      setShowSuggest(false);
    }
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const selectSuggestion = (item) => {
    if (!item) return;
    setSearchQuery((item.name || '').trim());
    setShowSuggest(false);
    onSearch();
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter') {
      if (showSuggest && activeIndex >= 0 && activeIndex < suggestions.length) {
        selectSuggestion(suggestions[activeIndex]);
      } else {
        setShowSuggest(false);
        setSuggestions([]);
        // Trim on submit
        setSearchQuery((prev) => prev.trim());
        onSearch();
      }
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === 'Escape') {
      setShowSuggest(false);
    }
  };

  const handleSearchClick = () => {
    setShowSuggest(false);
    setSuggestions([]);
    // Trim on submit
    setSearchQuery((prev) => prev.trim());
    onSearch();
  };

  return (
    <div className="search-bar">
      <div className="search-input-wrap">
        <input
          type="text"
          placeholder="Search products..."
          value={searchQuery}
          onKeyDown={handleKeyDown}
          onChange={(e) => setSearchQuery(e.target.value.replace(/^\s+/, ''))}
          onFocus={() => suggestions.length && setShowSuggest(true)}
          onBlur={() => setTimeout(() => setShowSuggest(false), 100)}
        />
        {showSuggest && suggestions.length > 0 && (
          <div className="autocomplete" role="listbox">
            {suggestions.map((s, idx) => (
              <div
                key={`${s.id}-${idx}`}
                className={`autocomplete-item ${idx === activeIndex ? 'active' : ''}`}
                role="option"
                aria-selected={idx === activeIndex}
                onMouseDown={(e) => { e.preventDefault(); selectSuggestion(s); }}
                onMouseEnter={() => setActiveIndex(idx)}
              >
                <span className="auto-name">{s.name}</span>
                {s.brand && <span className="auto-brand"> · {s.brand}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
      <button onClick={handleSearchClick}>Search</button>
    </div>
  );
};


const ProductCard = ({ product, searchTerm, products, onProductClick }) => {
  // Use a local fallback image to avoid external errors and flicker
  const defaultImage = "/placeholder-product.svg";

  const handleClick = () => {

    trackSearchClick({
      document: { id: product.id, index: "products-catalog"},
      search: {
        query: searchTerm,
        page: {
          current: 1,
          size: products.length,
        },
        results: {
          items: [
            {
              document: {
                id: product.id,
                index: "products-catalog",
              }
            },
          ],
          total_results: products.length,
        },
        search_application: "app-product-store"
      },
    });

    if (onProductClick) onProductClick(product.id);
  };

  return (
    <div className="product-card" onClick={handleClick}>
      <div className="product-image">
        <img
          src={product.image_link || defaultImage}
          alt={product.name}
          loading="lazy"
          onError={(e) => {
            // Prevent infinite loop if fallback also fails
            e.target.onerror = null;
            e.target.src = defaultImage;
          }}
        />
      </div>
      <div className="product-info">
        <h4>{product.name}</h4>
        <p>{product.description}</p>
        <p>{product.brand}</p>
        <span className="product-price">
          {product.currency ? product.currency : 'USD'} {parseFloat(product.price).toFixed(2)}
        </span>
        <div className="product-tags">
          {product.tags && product.tags.map((tag, index) => (
            <span key={index} className={`tag tag-${index % 5}`}>{tag}</span>
          ))}
        </div>
      </div>
    </div>
  );
};

const ProductList = ({ products, searchTerm, loading, onProductClick }) => {
  if (loading) {
    return (
      <div className="product-list">
        {[...Array(9)].map((_, i) => (
          <div key={i} className="product-card skeleton">
            <div className="product-image skeleton-box" />
            <div className="product-info">
              <div className="skeleton-line w-60" />
              <div className="skeleton-line w-90" />
              <div className="skeleton-line w-40" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="product-list">
      {Array.isArray(products) && products.length > 0 ? (
        products.map(product => (
          <ProductCard key={product.id} product={product} searchTerm={searchTerm} products={products} onProductClick={onProductClick} />
        ))
      ) : (
        <p>No products found</p>
      )}
    </div>
  );
};


const DetailsModal = ({ open, onClose, productId }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const defaultImage = '/placeholder-product.svg';

  useEffect(() => {
    let cancelled = false;
    const fetchDetails = async () => {
      if (!open || !productId) return;
      setLoading(true);
      setError(null);
      try {
        const res = await axios.get(`http://127.0.0.1:5000/api/products/id/${productId}`);
        if (!cancelled) setData(res.data);
      } catch (e) {
        if (!cancelled) setError('Failed to load product details');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchDetails();
    return () => { cancelled = true; };
  }, [open, productId]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{data?.name || 'Product details'}</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-content">
          {loading ? (
            <div className="modal-skeleton">
              <div className="skeleton-box modal-image" />
              <div className="skeleton-line w-80" />
              <div className="skeleton-line w-60" />
              <div className="skeleton-line w-90" />
            </div>
          ) : error ? (
            <div className="modal-error">{error}</div>
          ) : data ? (
            <div className="modal-body">
              <div className="modal-media">
                <img
                  src={data.image_link || defaultImage}
                  alt={data.name}
                  onError={(e) => { e.target.onerror = null; e.target.src = defaultImage; }}
                />
              </div>
              <div className="modal-details">
                <p className="modal-brand">{data.brand}</p>
                <p className="modal-category">{data.category} {data.product_type ? `• ${data.product_type}` : ''}</p>
                <p className="modal-price">{data.currency || 'USD'} {parseFloat(data.price).toFixed(2)}</p>
                {data.rating != null && (
                  <p className="modal-rating">Rating: {data.rating}/5</p>
                )}
                <p className="modal-description">{data.description}</p>
                {Array.isArray(data.tag_list) && data.tag_list.length > 0 && (
                  <div className="modal-tags">
                    {data.tag_list.map((t, i) => (
                      <span key={i} className={`tag tag-${i % 5}`}>{t}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};


const ProductPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [products, setProducts] = useState([]);
  const [facets, setFacets] = useState({ categories: [], product_types: [] });
  const [selectedFacets, setSelectedFacets] = useState({
    categories: [],
    productTypes: [],
    brands: []
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [isHybridSearch, setIsHybridSearch] = useState(false);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [activeProductId, setActiveProductId] = useState(null);
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') return saved;
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    return prefersDark ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));

  const openDetails = (id) => {
    setActiveProductId(id);
    setDetailOpen(true);
  };
  const closeDetails = () => setDetailOpen(false);

  const fetchProducts = useCallback(async () => {
    try {
      const response = await axios.get(`http://127.0.0.1:5000/api/products/search`, {
        params: {
          query: searchTerm,
          selectedCategories: selectedFacets.categories,
          selectedProductTypes: selectedFacets.productTypes,
          selectedBrands: selectedFacets.brands,
          hybrid: isHybridSearch
        }
      });
      setProducts(response.data);
      const documents = response.data.map(product => ({
        document: {
          id: product.id,
          index: "products-catalog"
        }
      }));
      trackSearch({
        search: {
          query: searchTerm,
          results: {
            items: documents,
            total_results: response.data.length,
          },
        },
      });
    } catch (error) {
      console.error('Failed to ger products', error);
    }
  }, [searchTerm, selectedFacets.categories, selectedFacets.productTypes, selectedFacets.brands, isHybridSearch]);

  const fetchFacets = useCallback(async () => {
    try {
      const response = await axios.get(`http://127.0.0.1:5000/api/products/facets`, {
        params: {
          query: searchTerm,
          selectedCategories: selectedFacets.categories,
          selectedProductTypes: selectedFacets.productTypes,
          selectedBrands: selectedFacets.brands,
          hybrid: isHybridSearch
        }
      });
      setFacets(response.data);
    } catch (error) {
      console.error('Failed to get facets', error);
    }
  }, [searchTerm, selectedFacets.categories, selectedFacets.productTypes, selectedFacets.brands, isHybridSearch]);

  // Track page view only on initial mount
  useEffect(() => {
    trackPageView({
      page: { title: "home-page" },
    });
  }, []);

  // Consolidated fetch to reduce flicker and avoid overlapping requests
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        await Promise.all([fetchFacets(), fetchProducts()]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [fetchFacets, fetchProducts]);

  const handleSearch = () => {
    // Only update the search term; useEffect will trigger fetching.
    setSearchTerm(searchQuery);
  };

  const handleFacetChange = (facetType, facetId) => {
    setSelectedFacets(prevState => {
      const selected = prevState[facetType].includes(facetId)
        ? prevState[facetType].filter(id => id !== facetId)
        : [...prevState[facetType], facetId];

      return {
        ...prevState,
        [facetType]: selected
      };
    });
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">◆</span>
          <span className="brand-name">Hybrid Search</span>
        </div>
        <div className="header-actions">
          <div className="hybrid-search-checkbox">
            <label>
              <input
                type="checkbox"
                checked={isHybridSearch}
                onChange={(e) => setIsHybridSearch(e.target.checked)}
              />
              Hybrid
            </label>
          </div>
          <button className="mode-toggle" onClick={toggleTheme} aria-label="Toggle color mode">
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </div>
      </header>

      <main className="product-page">
        <aside className="search-and-facets">
          <Facets
            categories={facets.categories}
            productTypes={facets.product_types}
            brands={facets.brands}
            selectedFacets={selectedFacets}
            onFacetChange={handleFacetChange}
          />
        </aside>
        <section className="product-section">
          <SearchBar
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            onSearch={handleSearch}
          />
          <ProductList products={products} searchTerm={searchTerm} loading={loading} onProductClick={openDetails} />
          <DetailsModal open={detailOpen} onClose={closeDetails} productId={activeProductId} />
        </section>
      </main>

      <footer className="app-footer">
        <div>© Hybrid Search • Built with Elasticsearch + React</div>
        <div className="footer-links">
          <a href="#" aria-label="Help">Help</a>
          <a href="#" aria-label="Privacy">Privacy</a>
        </div>
      </footer>
    </div>
  );
};

export default ProductPage;

