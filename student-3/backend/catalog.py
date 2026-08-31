"""
Mock product catalog for the AI Product Consultant.

In production this data would be served by the Catalog microservice. Here it is
an in-memory fixture. The agentic loop uses it in two places:

  * Plan    - `context_block()` is injected into the prompt so the model only
              ever sees products that genuinely exist.
  * Observe  - `VALID_IDS` / `get_many()` let the backend reject any answer that
              cites a product id that is not in this list (hallucination guard).
"""

PRODUCTS = [
    {
        "id": "LAP-001", "name": "Meridian Pro 16", "category": "Laptops",
        "brand": "Aeon", "price": 2399,
        "specs": "16-core CPU, 32GB RAM, 1TB SSD, 16in 4K display",
        "description": "Flagship creator laptop for 4K video editing and 3D work.",
    },
    {
        "id": "LAP-002", "name": "Meridian Air 13", "category": "Laptops",
        "brand": "Aeon", "price": 1199,
        "specs": "10-core CPU, 16GB RAM, 512GB SSD, 13in, 1.1kg, 18h battery",
        "description": "Ultralight everyday laptop with all-day battery life.",
    },
    {
        "id": "LAP-003", "name": "Nimbus Gaming 15", "category": "Laptops",
        "brand": "Vortex", "price": 1799,
        "specs": "8-core CPU, RTX-class GPU, 16GB RAM, 165Hz 1440p",
        "description": "Portable machine for high-refresh gaming and GPU compute.",
    },
    {
        "id": "PHN-001", "name": "Aura 12", "category": "Smartphones",
        "brand": "Lumen", "price": 999,
        "specs": "6.7in OLED 120Hz, triple camera, 256GB, titanium frame",
        "description": "Flagship phone with pro-grade cameras and long support.",
    },
    {
        "id": "PHN-002", "name": "Aura SE", "category": "Smartphones",
        "brand": "Lumen", "price": 449,
        "specs": "6.1in OLED, dual camera, 128GB, compact body",
        "description": "Compact flagship-feel phone at a mid-range price.",
    },
    {
        "id": "PHN-003", "name": "Pulse 5", "category": "Smartphones",
        "brand": "Rivet", "price": 279,
        "specs": "6.5in LCD 90Hz, 5000mAh battery, 128GB",
        "description": "Budget phone with excellent battery life.",
    },
    {
        "id": "TAB-001", "name": "Slate 11", "category": "Tablets",
        "brand": "Aeon", "price": 599,
        "specs": "11in 120Hz, 8GB RAM, 128GB, stylus support",
        "description": "Note-taking and media tablet aimed at students.",
    },
    {
        "id": "TAB-002", "name": "Slate Mini", "category": "Tablets",
        "brand": "Aeon", "price": 399,
        "specs": "8.3in, 4GB RAM, 128GB, 300g",
        "description": "Pocketable tablet for reading and travel.",
    },
    {
        "id": "MON-001", "name": "ClearView 27 4K", "category": "Monitors",
        "brand": "Optic", "price": 429,
        "specs": "27in IPS, 4K, 99% sRGB, USB-C 90W power delivery",
        "description": "Colour-accurate 4K monitor for creative work.",
    },
    {
        "id": "MON-002", "name": "ClearView 34 UW", "category": "Monitors",
        "brand": "Optic", "price": 699,
        "specs": "34in ultrawide, 144Hz, HDR400, curved",
        "description": "Ultrawide display for gaming and multitasking.",
    },
    {
        "id": "AUD-001", "name": "EchoBuds Pro", "category": "Headphones",
        "brand": "Sonic", "price": 199,
        "specs": "ANC true wireless, 30h total, IP54, wireless charging",
        "description": "Noise-cancelling earbuds for commuting and calls.",
    },
    {
        "id": "AUD-002", "name": "EchoStudio Over-Ear", "category": "Headphones",
        "brand": "Sonic", "price": 349,
        "specs": "ANC over-ear, 40h battery, LDAC, memory foam",
        "description": "Reference wireless headphones for critical listening.",
    },
    {
        "id": "AUD-003", "name": "FieldMic Headset", "category": "Headphones",
        "brand": "Sonic", "price": 129,
        "specs": "Gaming headset, detachable boom mic, 7.1 spatial, USB-C",
        "description": "Comfortable headset with a clear broadcast-quality mic.",
    },
    {
        "id": "CAM-001", "name": "Vista X100", "category": "Cameras",
        "brand": "Pixel", "price": 899,
        "specs": "APS-C sensor, 26MP, 4K60 video, fixed 23mm prime",
        "description": "Premium compact camera for travel and street photography.",
    },
    {
        "id": "WEAR-001", "name": "Tempo Watch 2", "category": "Smartwatches",
        "brand": "Lumen", "price": 329,
        "specs": "AMOLED, dual-band GPS, 7-day battery, ECG and SpO2",
        "description": "Health and fitness smartwatch with long battery life.",
    },
    {
        "id": "SPK-001", "name": "BoomBox Go", "category": "Speakers",
        "brand": "Sonic", "price": 149,
        "specs": "Portable Bluetooth speaker, IP67, 24h playtime, stereo pair",
        "description": "Rugged portable speaker with a big low end for its size.",
    },
    {
        "id": "STOR-001", "name": "WarpDrive 2TB SSD", "category": "Storage",
        "brand": "Byte", "price": 179,
        "specs": "External NVMe, 2000MB/s, USB-C, pocket size",
        "description": "Fast external SSD for editing scratch disks and backups.",
    },
    {
        "id": "SMH-001", "name": "HomeHub Starter Kit", "category": "Smart Home",
        "brand": "OmniTech", "price": 249,
        "specs": "hub, 3 smart bulbs, smart plug, motion sensor, app and voice control",
        "description": "Everything to begin automating the lighting and power in "
                       "one room; expandable later.",
    },
]

BY_ID = {p["id"]: p for p in PRODUCTS}
VALID_IDS = set(BY_ID)


def all_products():
    """Return the full catalog."""
    return list(PRODUCTS)


def get(product_id):
    """Return a single product dict or None."""
    return BY_ID.get(product_id)


def get_many(product_ids):
    """Resolve an iterable of ids to product dicts, dropping unknown ids and
    preserving the given order."""
    seen, out = set(), []
    for pid in product_ids:
        if pid in BY_ID and pid not in seen:
            seen.add(pid)
            out.append(BY_ID[pid])
    return out


def unknown_ids(product_ids):
    """Return the ids that are NOT in the catalog."""
    return [pid for pid in product_ids if pid not in BY_ID]


_STOPWORDS = {
    "the", "for", "and", "with", "that", "this", "you", "your", "need", "needs",
    "want", "wants", "best", "good", "great", "under", "over", "about", "any",
    "can", "get", "got", "have", "has", "would", "should", "could", "please",
    "looking", "recommend", "recommendation", "help", "something",
    "around", "what", "which", "who", "how",
}

# Words that map a request onto a catalog category even if phrased loosely.
_CATEGORY_HINTS = {
    "laptop": "Laptops", "notebook": "Laptops", "macbook": "Laptops",
    "phone": "Smartphones", "smartphone": "Smartphones", "iphone": "Smartphones",
    "android": "Smartphones", "tablet": "Tablets", "ipad": "Tablets",
    "monitor": "Monitors", "display": "Monitors", "screen": "Monitors",
    "headphone": "Headphones", "headphones": "Headphones", "headset": "Headphones",
    "earbuds": "Headphones", "earphones": "Headphones",
    "camera": "Cameras", "watch": "Smartwatches", "smartwatch": "Smartwatches",
    "speaker": "Speakers", "drive": "Storage", "ssd": "Storage", "storage": "Storage",
}

# Multi-word phrases that point at a category (checked against the raw query).
_PHRASE_HINTS = {
    "smart home": "Smart Home",
    "home automation": "Smart Home",
    "smart lighting": "Smart Home",
    "smart bulb": "Smart Home",
    "video doorbell": "Smart Home",
}


def search(query, limit=6):
    """Rank the catalog against a free-text query.

    Deterministic keyword scoring - also used as the offline fallback answer
    when Ollama is unreachable, so the feature keeps working without a model.
    """
    ql = (query or "").lower()
    raw = [t.strip(".,!?;:$()'\"").lower() for t in ql.split()]
    tokens = {t for t in raw if len(t) > 2 and t not in _STOPWORDS}
    hinted = {_CATEGORY_HINTS[t] for t in raw if t in _CATEGORY_HINTS}
    hinted |= {cat for phrase, cat in _PHRASE_HINTS.items() if phrase in ql}
    # "smart home" must not also be read as "smartphone"
    if "Smart Home" in hinted:
        tokens.discard("smart")

    scored = []
    for product in PRODUCTS:
        name_cat = f"{product['name']} {product['category']} {product['brand']}".lower()
        detail = f"{product['specs']} {product['description']}".lower()
        score = 3 * sum(1 for t in tokens if t in name_cat)
        score += sum(1 for t in tokens if t in detail)
        if product["category"] in hinted:
            score += 5
        if score:
            scored.append((score, product))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    ranked = [p for _, p in scored[:limit]]
    return ranked or PRODUCTS[:limit]


def context_block(products=None):
    """Plain-text catalog listing for injection into the LLM prompt."""
    products = products if products is not None else PRODUCTS
    lines = []
    for p in products:
        lines.append(
            f"- {p['id']} | {p['name']} | {p['category']} | ${p['price']} | {p['specs']}"
        )
    return "\n".join(lines)
