#!/usr/bin/env python3
"""
Vehicle Tracker — Tacoma scraper consolidated from tacoma-hunter repo.
Scrapes CarGurus and Cars.com for 2020-2023 Toyota Tacoma Double Cab Long Bed 4WD.
Deduplicates via MD5 cache in data/tacoma_cache.json.
"""

import json
import re
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPE_DEPS = True
except ImportError:
    _SCRAPE_DEPS = False

log = logging.getLogger("vehicle_tracker")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

WESTERN_STATES = [
    "NM", "CO", "UT", "AZ", "NV", "CA", "OR", "WA", "TX", "ID", "WY", "MT",
    "New Mexico", "Colorado", "Utah", "Arizona", "Nevada", "California",
    "Oregon", "Washington", "Texas", "Idaho", "Wyoming", "Montana",
    "Taos", "Albuquerque", "Santa Fe", "Denver", "Salt Lake", "Phoenix",
    "Las Vegas", "Los Angeles", "Portland", "Seattle", "Boise", "El Paso",
    "Tucson", "San Diego", "Sacramento", "Reno", "Bend", "Lakewood",
    "Wheat Ridge", "Brighton", "Saint George", "Flagstaff", "Durango",
]

LONG_BED_KEYWORDS = ["LB", "Long Bed", "6 ft", "6'", "6-ft", "6 Bed", "6-foot"]
TARGET_TRIMS = ["TRD Off-Road", "TRD Off Road", "TRD Sport", "SR5"]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache(data_dir: Path) -> dict:
    cache_file = data_dir / "tacoma_cache.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(data_dir: Path, cache: dict):
    cache_file = data_dir / "tacoma_cache.json"
    cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _listing_id(listing: dict) -> str:
    raw = f"{listing.get('title','')}-{listing.get('price','')}-{listing.get('miles','')}-{listing.get('location','')}"
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_price(s: str) -> int | None:
    if not s: return None
    digits = re.sub(r"[^\d]", "", str(s))
    if digits:
        v = int(digits)
        if 10000 < v < 100000:
            return v
    return None


def _parse_miles(s: str) -> int | None:
    if not s: return None
    digits = re.sub(r"[^\d]", "", str(s))
    if digits:
        v = int(digits)
        if 0 < v < 500000:
            return v
    return None


def _is_long_bed(title: str) -> bool:
    t = (title or "").upper()
    return any(kw.upper() in t for kw in LONG_BED_KEYWORDS)


# ---------------------------------------------------------------------------
# Scrapers
# ---------------------------------------------------------------------------

def _scrape_cargurus(max_price: int, max_miles: int, min_year: int, max_year: int,
                     session: requests.Session | None = None) -> list:
    session = session or requests.Session()
    listings = []
    search_urls = [
        (f"https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action"
         f"?sourceContext=carGurusHomePageModel&entitySelectingHelper.selectedEntity=t88828"
         f"&zip=87571&distance=50000&startYear={min_year}&endYear={max_year}"
         f"&maxPrice={max_price}&maxMileage={max_miles}&sortDir=ASC&sortType=DEAL"),
        (f"https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action"
         f"?sourceContext=carGurusHomePageModel&entitySelectingHelper.selectedEntity=t88830"
         f"&zip=87571&distance=50000&startYear={min_year}&endYear={max_year}"
         f"&maxPrice={max_price}&maxMileage={max_miles}&sortDir=ASC&sortType=DEAL"),
        (f"https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action"
         f"?sourceContext=carGurusHomePageModel&entitySelectingHelper.selectedEntity=t88826"
         f"&zip=87571&distance=50000&startYear={min_year}&endYear={max_year}"
         f"&maxPrice={max_price}&maxMileage={max_miles}&sortDir=ASC&sortType=DEAL"),
    ]
    for url in search_urls:
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            page = resp.text

            # JSON-LD extraction
            soup = BeautifulSoup(page, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") in ("Car", "Vehicle"):
                            listings.append({
                                "title": item.get("name", ""),
                                "price": str(item.get("offers", {}).get("price", "")),
                                "miles": str(item.get("mileageFromOdometer", {}).get("value", "")),
                                "location": item.get("offers", {}).get("availableAtOrFrom", {}).get("address", {}).get("addressRegion", ""),
                                "url": item.get("url", ""),
                                "source": "CarGurus",
                            })
                except (json.JSONDecodeError, TypeError, AttributeError):
                    continue

            # Inline JS extraction via VIN pattern
            vin_pat = re.compile(r'"vin"\s*:\s*"([A-HJ-NPR-Z0-9]{17})"')
            title_pat = re.compile(r'"carTitle"\s*:\s*"([^"]+)"')
            price_pat = re.compile(r'"price"\s*:\s*(\d{4,6})')
            miles_pat = re.compile(r'"mileage"\s*:\s*(\d{3,6})')
            url_pat = re.compile(r'"listingDetailUrl"\s*:\s*"([^"]+)"')
            loc_pat = re.compile(r'"dealerCity"\s*:\s*"([^"]+)"[^}]*"dealerState"\s*:\s*"([^"]+)"')

            for vm in vin_pat.finditer(page):
                ctx = page[max(0, vm.start()-1000):min(len(page), vm.end()+1000)]
                tm = title_pat.search(ctx)
                pm = price_pat.search(ctx)
                mm = miles_pat.search(ctx)
                um = url_pat.search(ctx)
                lm = loc_pat.search(ctx)
                if tm and pm:
                    listings.append({
                        "title": tm.group(1),
                        "price": pm.group(1),
                        "miles": mm.group(1) if mm else "",
                        "location": f"{lm.group(1)}, {lm.group(2)}" if lm else "",
                        "url": f"https://www.cargurus.com{um.group(1)}" if um else "",
                        "vin": vm.group(1),
                        "source": "CarGurus",
                    })
        except Exception as e:
            log.warning(f"CarGurus error: {e}")
    return listings


def _scrape_carscom(max_price: int, max_miles: int, min_year: int, max_year: int,
                    session: requests.Session | None = None) -> list:
    session = session or requests.Session()
    listings = []
    trim_slugs = [
        ("toyota-tacoma-trd_off_road", "long+bed"),
        ("toyota-tacoma-trd_sport",    "long+bed"),
        ("toyota-tacoma-sr5",          "long+bed+V6"),
    ]
    for trim_slug, kw in trim_slugs:
        url = (
            f"https://www.cars.com/shopping/results/"
            f"?dealer_id=&keyword={kw}&list_price_max={max_price}"
            f"&makes[]=toyota&maximum_distance=all&mileage_max={max_miles}"
            f"&models[]=toyota-tacoma&page_size=20&sort=best_match_desc&stock_type=used"
            f"&trims[]={trim_slug}&year_max={max_year}&year_min={min_year}"
        )
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            cards = soup.select("div.vehicle-card") or soup.select('[class*="vehicle-card"]')
            for card in cards:
                try:
                    te = card.select_one("h2") or card.select_one('[class*="title"]')
                    pe = card.select_one('[class*="primary-price"]') or card.select_one('[class*="price"]')
                    me = card.select_one('[class*="mileage"]')
                    le = card.select_one('[class*="dealer-name"]')
                    ae = card.select_one("a[href]")
                    title = te.get_text(strip=True) if te else ""
                    if title:
                        listings.append({
                            "title": title,
                            "price": pe.get_text(strip=True) if pe else "",
                            "miles": me.get_text(strip=True) if me else "",
                            "location": le.get_text(strip=True) if le else "",
                            "url": f"https://www.cars.com{ae['href']}" if ae and ae.get("href") else "",
                            "source": "Cars.com",
                        })
                except (AttributeError, TypeError, KeyError):
                    continue

            # JSON-LD fallback
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    for item in (data if isinstance(data, list) else [data]):
                        if item.get("@type") in ("Car", "Vehicle", "Product"):
                            listings.append({
                                "title": item.get("name", ""),
                                "price": str(item.get("offers", {}).get("price", "")),
                                "miles": str(item.get("mileageFromOdometer", {}).get("value", "")),
                                "location": "",
                                "url": item.get("url", ""),
                                "source": "Cars.com",
                            })
                except (json.JSONDecodeError, TypeError, AttributeError):
                    continue
        except Exception as e:
            log.warning(f"Cars.com error: {e}")
    return listings


def _filter_listings(raw: list, max_price: int, max_miles: int) -> list:
    filtered, seen = [], set()
    for lst in raw:
        lid = _listing_id(lst)
        if lid in seen:
            continue
        seen.add(lid)

        price = _parse_price(lst.get("price", ""))
        miles = _parse_miles(lst.get("miles", ""))

        if price and price > max_price:
            continue
        if miles and miles > max_miles:
            continue

        title_up = (lst.get("title", "")).upper()
        if not any(kw in title_up for kw in ["4WD", "4X4", "FOUR-WHEEL", "FOUR WHEEL", "AWD"]):
            lst["note"] = "verify 4WD"

        lst["bed"] = "✅ Long Bed" if _is_long_bed(lst.get("title","")) else "❓ Verify bed"
        lst["price_num"] = price
        lst["miles_num"] = miles
        filtered.append(lst)

    filtered.sort(key=lambda x: (x.get("price_num") or 99999, x.get("miles_num") or 99999))
    return filtered


def _find_new(filtered: list, cache: dict) -> list:
    new = []
    for lst in filtered:
        lid = _listing_id(lst)
        if lid not in cache:
            new.append(lst)
            cache[lid] = {
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "title": lst.get("title", ""),
                "price": lst.get("price", ""),
            }
    return new


def _fb_links() -> list:
    return [
        {"title": "FB Marketplace — Tacoma LB 4WD (Albuquerque)", "url": "https://www.facebook.com/marketplace/albuquerque/search?query=tacoma%20long%20bed%204wd&minPrice=20000&maxPrice=40000"},
        {"title": "FB Marketplace — Tacoma LB 4WD (Denver)",      "url": "https://www.facebook.com/marketplace/denver/search?query=tacoma%20long%20bed%204wd&minPrice=20000&maxPrice=40000"},
        {"title": "FB Marketplace — Tacoma LB 4WD (Salt Lake)",    "url": "https://www.facebook.com/marketplace/salt-lake-city/search?query=tacoma%20long%20bed%204wd&minPrice=20000&maxPrice=40000"},
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_tacoma_search(data_dir: Path) -> tuple:
    """
    Run full Tacoma search: scrape, filter, dedup, save cache.
    Returns (new_listings, all_listings, fb_urls).
    Raises ImportError if requests/beautifulsoup4 not installed.
    """
    if not _SCRAPE_DEPS:
        raise ImportError("requests and beautifulsoup4 are required for vehicle_tracker")

    try:
        cfg = json.loads((data_dir / "constraints.json").read_text(encoding="utf-8"))
        vs = cfg["vehicle_search"]
        max_price = vs.get("max_price", 40000)
        max_miles = vs.get("max_miles", 60000)
        years = vs.get("years", [2020, 2021, 2022, 2023])
        min_year, max_year = min(years), max(years)
    except Exception:
        max_price, max_miles, min_year, max_year = 40000, 60000, 2020, 2023

    cache = _load_cache(data_dir)

    session = requests.Session()
    session.headers.update(HEADERS)

    raw = []
    log.info("Scraping CarGurus + Cars.com concurrently...")
    with ThreadPoolExecutor(max_workers=2) as pool:
        cg_future = pool.submit(
            _scrape_cargurus, max_price, max_miles,
            min_year, max_year, session,
        )
        cc_future = pool.submit(
            _scrape_carscom, max_price, max_miles,
            min_year, max_year, session,
        )
        raw.extend(cg_future.result())
        raw.extend(cc_future.result())
    log.info(f"Raw: {len(raw)} listings")

    filtered = _filter_listings(raw, max_price, max_miles)
    log.info(f"Filtered: {len(filtered)} listings")

    new_listings = _find_new(filtered, cache)
    _save_cache(data_dir, cache)

    return new_listings, filtered, _fb_links()
