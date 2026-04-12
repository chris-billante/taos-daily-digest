#!/usr/bin/env python3
"""
Land Tracker — multi-source land listing scraper for Taos County.
Tier 1: Direct scrape (LandFlip) — free, always runs.
Tier 2: Apify actors (LandWatch, Zillow, Redfin) — credit-gated.
Tier 3: Manual search links for sources not yet automated.
Deduplicates via MD5 cache in data/land_cache.json.
"""

import hashlib
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPE_DEPS = True
except ImportError:
    _SCRAPE_DEPS = False

try:
    from apify_client import ApifyClient
    _APIFY_DEPS = True
except ImportError:
    _APIFY_DEPS = False

log = logging.getLogger("land_tracker")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

LANDFLIP_BASE = (
    "https://www.landflip.com/land-for-sale"
    "/new-mexico/taos-county"
)


# -------------------------------------------------------------------
# Cache helpers
# -------------------------------------------------------------------

def _load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_cache(cache: dict, cache_path: Path) -> None:
    cache_path.write_text(
        json.dumps(cache, indent=2), encoding="utf-8"
    )


# -------------------------------------------------------------------
# Pure helpers (testable, no I/O)
# -------------------------------------------------------------------

def _parse_price(s: str | None) -> int | None:
    """Extract dollar price from text. Returns None for unparseable."""
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", str(s))
    if not digits:
        return None
    v = int(digits)
    if 100 < v < 10_000_000:
        return v
    return None


def _parse_acres(s: str | None) -> float | None:
    """Extract acreage from text like '5.2 Acres' or '10 ac'."""
    if not s:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:acres?|ac\b)?", str(s), re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _listing_id(listing: dict) -> str:
    """MD5 hash for dedup across sources."""
    raw = (
        f"{listing.get('title', '')}-"
        f"{listing.get('price', '')}-"
        f"{listing.get('acres', '')}-"
        f"{listing.get('location', '')}"
    )
    return hashlib.md5(raw.encode()).hexdigest()


def _filter_listings(
    raw: list[dict],
    min_acres: float,
    max_price: int,
    target_areas: list[str],
) -> list[dict]:
    """Filter, annotate, deduplicate, and sort listings."""
    filtered: list[dict] = []
    seen: set[str] = set()

    for lst in raw:
        lid = _listing_id(lst)
        if lid in seen:
            continue
        seen.add(lid)

        price = _parse_price(lst.get("price", ""))
        acres = _parse_acres(lst.get("acres", ""))

        if price is not None and price > max_price:
            continue
        if acres is not None and acres < min_acres:
            continue

        lst["price_num"] = price
        lst["acres_num"] = acres

        # Flag target-area matches
        loc = (lst.get("location", "") or "").lower()
        title = (lst.get("title", "") or "").lower()
        combined = f"{loc} {title}"
        lst["priority"] = any(
            area.lower() in combined for area in target_areas
        )

        # High-priority flag: under $50K with water
        water = (lst.get("water", "") or "").lower()
        has_water = water and water not in ("none", "unknown", "no", "")
        if price is not None and price < 50_000 and has_water:
            lst["high_priority"] = True

        filtered.append(lst)

    filtered.sort(key=lambda x: (
        not x.get("high_priority", False),
        not x.get("priority", False),
        x.get("price_num") or 999_999_999,
    ))
    return filtered


def _find_new(filtered: list[dict], cache: dict) -> list[dict]:
    """Return listings not yet in cache; update cache in place."""
    new = []
    for lst in filtered:
        lid = _listing_id(lst)
        if lid not in cache:
            new.append(lst)
            cache[lid] = {
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "title": lst.get("title", ""),
                "price": lst.get("price", ""),
                "source": lst.get("source", ""),
            }
    return new


def _deduplicate_across_sources(listings: list[dict]) -> list[dict]:
    """Merge same-parcel listings from different sources."""
    seen: dict[str, dict] = {}
    for lst in listings:
        # Normalize key: strip whitespace, lowercase
        norm_title = re.sub(r"\s+", " ", (lst.get("title", "")).strip().lower())
        norm_price = re.sub(r"[^\d]", "", str(lst.get("price", "")))
        norm_acres = str(lst.get("acres", "")).strip().lower()
        key = f"{norm_title}|{norm_price}|{norm_acres}"
        if key in seen:
            existing = seen[key]
            existing_sources = existing.get("source", "")
            new_source = lst.get("source", "")
            if new_source and new_source not in existing_sources:
                existing["source"] = f"{existing_sources}, {new_source}"
        else:
            seen[key] = lst
    return list(seen.values())


# -------------------------------------------------------------------
# Tier 3: Manual links (always available, free)
# -------------------------------------------------------------------

def _manual_links() -> list[dict]:
    return [
        {
            "title": "Land.com — Taos County",
            "url": (
                "https://www.land.com/"
                "Taos-County-NM/undeveloped-land/"
            ),
        },
        {
            "title": "LandSearch — Off-Grid Taos",
            "url": (
                "https://www.landsearch.com/"
                "off-grid/taos-county-nm"
            ),
        },
        {
            "title": "Realtor.com — Taos County Land",
            "url": (
                "https://www.realtor.com/"
                "realestateandhomes-search/"
                "Taos-County_NM/type-land"
            ),
        },
        {
            "title": "LandWatch — Taos County",
            "url": (
                "https://www.landwatch.com/"
                "new-mexico-land-for-sale/taos-county"
            ),
        },
    ]


# -------------------------------------------------------------------
# Tier 1: LandFlip (direct scrape, free)
# -------------------------------------------------------------------

def _scrape_landflip(
    max_pages: int = 3,
    session: requests.Session | None = None,
) -> list[dict]:
    """Scrape LandFlip server-rendered HTML for Taos County."""
    if not _SCRAPE_DEPS:
        log.warning("requests/bs4 not installed, skipping LandFlip")
        return []

    session = session or requests.Session()
    session.headers.update(HEADERS)
    listings: list[dict] = []

    for page in range(1, max_pages + 1):
        url = LANDFLIP_BASE if page == 1 else f"{LANDFLIP_BASE}/{page}-p"
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Try JSON-LD first (structured data)
            for script in soup.find_all(
                "script", type="application/ld+json"
            ):
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        itype = item.get("@type", "")
                        if itype in (
                            "Product", "RealEstateListing", "Offer"
                        ):
                            offer = item.get("offers", {})
                            if isinstance(offer, list):
                                offer = offer[0] if offer else {}
                            listings.append({
                                "title": item.get("name", ""),
                                "price": str(
                                    offer.get("price", "")
                                ),
                                "acres": "",
                                "location": (
                                    item.get("address", {})
                                    .get("addressLocality", "")
                                ),
                                "url": item.get("url", ""),
                                "source": "LandFlip",
                            })
                except (json.JSONDecodeError, TypeError):
                    continue

            # HTML card fallback
            cards = (
                soup.select("div.listing-card")
                or soup.select("div.property-card")
                or soup.select('[class*="listing"]')
            )
            for card in cards:
                try:
                    title_el = (
                        card.select_one("h2")
                        or card.select_one("h3")
                        or card.select_one('[class*="title"]')
                    )
                    price_el = card.select_one('[class*="price"]')
                    acres_el = (
                        card.select_one('[class*="acre"]')
                        or card.select_one('[class*="size"]')
                    )
                    loc_el = card.select_one('[class*="location"]')
                    link_el = card.select_one("a[href]")

                    title = (
                        title_el.get_text(strip=True)
                        if title_el else ""
                    )
                    if not title:
                        continue

                    href = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        if href.startswith("/"):
                            href = f"https://www.landflip.com{href}"

                    listings.append({
                        "title": title,
                        "price": (
                            price_el.get_text(strip=True)
                            if price_el else ""
                        ),
                        "acres": (
                            acres_el.get_text(strip=True)
                            if acres_el else ""
                        ),
                        "location": (
                            loc_el.get_text(strip=True)
                            if loc_el else ""
                        ),
                        "url": href,
                        "source": "LandFlip",
                    })
                except (AttributeError, TypeError, KeyError):
                    continue

        except requests.RequestException as e:
            log.warning("LandFlip page %d error: %s", page, e)
            break

    log.info("LandFlip: %d raw listings", len(listings))
    return listings


# -------------------------------------------------------------------
# Apify shared helper
# -------------------------------------------------------------------

def _run_apify_actor(
    actor_id: str, run_input: dict
) -> list[dict]:
    """Run an Apify actor and return dataset items."""
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        return []
    if not _APIFY_DEPS:
        log.warning("apify-client not installed, skipping actor %s", actor_id)
        return []

    client = ApifyClient(token)
    run = client.actor(actor_id).call(run_input=run_input)
    items = list(
        client.dataset(run["defaultDatasetId"]).iterate_items()
    )
    log.info("Apify actor %s: %d items", actor_id, len(items))
    return items


# -------------------------------------------------------------------
# Tier 2: LandWatch via Apify Website Content Crawler
# -------------------------------------------------------------------

def _scrape_landwatch_apify() -> list[dict]:
    """Crawl LandWatch via Apify Website Content Crawler."""
    items = _run_apify_actor(
        "apify/website-content-crawler",
        {
            "startUrls": [{
                "url": (
                    "https://www.landwatch.com/"
                    "new-mexico-land-for-sale/taos-county"
                ),
            }],
            "maxCrawlPages": 5,
            "crawlerType": "cheerio",
        },
    )
    return _parse_crawler_items(items, "LandWatch")


def _parse_crawler_items(
    items: list[dict], source: str
) -> list[dict]:
    """Parse Website Content Crawler output into listings."""
    listings: list[dict] = []
    for item in items:
        text = item.get("text", "") or item.get("markdown", "")
        if not text:
            continue
        # Look for listing-like patterns in the crawled text
        # Price pattern: $XX,XXX
        price_matches = re.findall(
            r"\$[\d,]+(?:\.\d{2})?", text
        )
        # Acreage pattern: X.X acres
        acre_matches = re.findall(
            r"([\d,.]+)\s*(?:acres?|ac)\b", text, re.I
        )
        # Location pattern: city/area names near Taos
        url = item.get("url", "")

        if price_matches and acre_matches:
            # Each price+acre pair is a potential listing
            for i in range(min(len(price_matches), len(acre_matches))):
                listings.append({
                    "title": "Land in Taos County",
                    "price": price_matches[i],
                    "acres": f"{acre_matches[i]} acres",
                    "location": "Taos County, NM",
                    "url": url,
                    "source": source,
                })
    log.info("%s (Apify): %d parsed listings", source, len(listings))
    return listings


# -------------------------------------------------------------------
# Tier 2: Zillow via Apify
# -------------------------------------------------------------------

def _scrape_zillow_apify() -> list[dict]:
    """Scrape Zillow land listings via Apify actor."""
    items = _run_apify_actor(
        "maxcopilot/zillow-scraper",
        {
            "searchUrls": [{
                "url": (
                    "https://www.zillow.com/"
                    "taos-county-nm/land/"
                ),
            }],
            "maxItems": 50,
        },
    )
    return _parse_zillow_items(items)


def _parse_zillow_items(items: list[dict]) -> list[dict]:
    """Parse Zillow actor structured output."""
    listings: list[dict] = []
    for item in items:
        price = (
            item.get("price")
            or item.get("unformattedPrice")
            or ""
        )
        address = (
            item.get("address")
            or item.get("streetAddress")
            or ""
        )
        acres = item.get("lotAreaValue", "") or item.get("lotSize", "")
        url = item.get("detailUrl") or item.get("url", "")
        if url and not url.startswith("http"):
            url = f"https://www.zillow.com{url}"

        if price or address:
            listings.append({
                "title": address or "Zillow Land Listing",
                "price": str(price),
                "acres": str(acres),
                "location": "Taos County, NM",
                "url": url,
                "source": "Zillow",
                "water": item.get("waterSource", ""),
            })
    log.info("Zillow (Apify): %d parsed listings", len(listings))
    return listings


# -------------------------------------------------------------------
# Tier 2: Redfin via Apify
# -------------------------------------------------------------------

def _scrape_redfin_apify() -> list[dict]:
    """Scrape Redfin land listings via Apify Website Content Crawler."""
    items = _run_apify_actor(
        "apify/website-content-crawler",
        {
            "startUrls": [{
                "url": (
                    "https://www.redfin.com/county/2921/"
                    "NM/Taos-County/"
                    "filter/property-type=land"
                ),
            }],
            "maxCrawlPages": 5,
            "crawlerType": "cheerio",
        },
    )
    return _parse_crawler_items(items, "Redfin")


# -------------------------------------------------------------------
# Constraints loader
# -------------------------------------------------------------------

def _load_constraints(data_dir: Path) -> dict:
    """Load land constraints from env or file."""
    import base64
    b64 = os.environ.get("PROJECT_CONSTRAINTS", "")
    if b64:
        return json.loads(base64.b64decode(b64))
    constraints_path = data_dir / "constraints.json"
    if constraints_path.exists():
        return json.loads(
            constraints_path.read_text(encoding="utf-8")
        )
    return {}


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def run_land_search(
    data_dir: Path,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Scrape multiple sources for Taos County land listings.

    Returns:
        (new_listings, all_listings, manual_links)
    """
    if not _SCRAPE_DEPS:
        raise ImportError(
            "requests and beautifulsoup4 required for land_tracker"
        )

    cache = _load_cache(data_dir / "land_cache.json")
    raw: list[dict] = []

    # Tier 1 — always runs (free)
    raw.extend(_scrape_landflip())

    # Tier 2 — Apify sources (credit-gated)
    if os.environ.get("APIFY_TOKEN"):
        apify_scrapers = [
            _scrape_landwatch_apify,
            _scrape_zillow_apify,
            _scrape_redfin_apify,
        ]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(fn) for fn in apify_scrapers]
            for f in as_completed(futs):
                try:
                    raw.extend(f.result())
                except Exception as e:
                    log.warning("Apify source failed: %s", e)
    else:
        log.info("APIFY_TOKEN not set, skipping Tier 2 sources")

    # Deduplicate across sources
    raw = _deduplicate_across_sources(raw)

    # Load filter params
    constraints = _load_constraints(data_dir)
    land = constraints.get("land", {})
    min_acres = land.get("min_acres", 2)
    max_price = land.get("max_price", 60_000)
    target_areas = land.get("target_areas", [])

    filtered = _filter_listings(raw, min_acres, max_price, target_areas)
    new = _find_new(filtered, cache)
    _save_cache(cache, data_dir / "land_cache.json")

    log.info(
        "Land search: %d new / %d total / %d manual links",
        len(new), len(filtered), len(_manual_links()),
    )
    return new, filtered, _manual_links()
