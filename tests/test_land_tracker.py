"""Tests for land_tracker.py pure helper functions."""

import hashlib

from land_tracker import (
    _deduplicate_across_sources,
    _filter_listings,
    _find_new,
    _listing_id,
    _manual_links,
    _parse_acres,
    _parse_price,
)

# --- _parse_price ---

class TestParsePrice:
    def test_dollar_format(self):
        assert _parse_price("$35,000") == 35000

    def test_plain_number(self):
        assert _parse_price("35000") == 35000

    def test_with_text(self):
        assert _parse_price("Price: $42,500") == 42500

    def test_low_land_price(self):
        """Land can be cheap — $5K is valid."""
        assert _parse_price("$5,000") == 5000

    def test_very_low_excluded(self):
        assert _parse_price("$50") is None

    def test_high_price(self):
        assert _parse_price("$500,000") == 500000

    def test_above_range(self):
        assert _parse_price("$10,000,000") is None

    def test_empty_string(self):
        assert _parse_price("") is None

    def test_none(self):
        assert _parse_price(None) is None

    def test_no_digits(self):
        assert _parse_price("no price listed") is None

    def test_price_with_cents(self):
        assert _parse_price("$29,900.00") == 2990000

    def test_ask_price(self):
        assert _parse_price("Asking $45,000") == 45000


# --- _parse_acres ---

class TestParseAcres:
    def test_simple_acres(self):
        assert _parse_acres("5 acres") == 5.0

    def test_decimal_acres(self):
        assert _parse_acres("2.5 Acres") == 2.5

    def test_large_acreage(self):
        assert _parse_acres("40.0 acres") == 40.0

    def test_ac_abbreviation(self):
        assert _parse_acres("10 ac") == 10.0

    def test_no_suffix(self):
        """Bare number still parses."""
        assert _parse_acres("5.5") == 5.5

    def test_with_comma(self):
        assert _parse_acres("1,200 acres") == 1200.0

    def test_empty_string(self):
        assert _parse_acres("") is None

    def test_none(self):
        assert _parse_acres(None) is None

    def test_no_number(self):
        assert _parse_acres("no acreage") is None

    def test_single_acre(self):
        assert _parse_acres("1 Acre") == 1.0


# --- _listing_id ---

class TestListingId:
    def test_deterministic(self):
        listing = {
            "title": "Land", "price": "35000",
            "acres": "5", "location": "Taos",
        }
        assert _listing_id(listing) == _listing_id(listing)

    def test_different_price_different_hash(self):
        a = {
            "title": "Land", "price": "35000",
            "acres": "5", "location": "Taos",
        }
        b = {
            "title": "Land", "price": "45000",
            "acres": "5", "location": "Taos",
        }
        assert _listing_id(a) != _listing_id(b)

    def test_missing_keys(self):
        result = _listing_id({})
        assert isinstance(result, str)
        assert len(result) == 32

    def test_known_hash(self):
        listing = {
            "title": "T", "price": "1",
            "acres": "2", "location": "X",
        }
        expected = hashlib.md5(b"T-1-2-X").hexdigest()
        assert _listing_id(listing) == expected


# --- _filter_listings ---

def _make_listing(
    title="Land in Taos County",
    price="$35,000",
    acres="5 acres",
    location="Tres Piedras, NM",
    url="https://example.com/listing",
    source="Test",
    water="",
):
    return {
        "title": title, "price": price, "acres": acres,
        "location": location, "url": url, "source": source,
        "water": water,
    }


class TestFilterListings:
    def test_filters_over_max_price(self):
        listings = [_make_listing(price="$70,000")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=["Tres Piedras"],
        )
        assert len(result) == 0

    def test_keeps_under_max_price(self):
        listings = [_make_listing(price="$35,000")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=["Tres Piedras"],
        )
        assert len(result) == 1

    def test_filters_under_min_acres(self):
        listings = [_make_listing(acres="1 acre")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=["Tres Piedras"],
        )
        assert len(result) == 0

    def test_keeps_over_min_acres(self):
        listings = [_make_listing(acres="5 acres")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=["Tres Piedras"],
        )
        assert len(result) == 1

    def test_deduplicates(self):
        lst = _make_listing()
        result = _filter_listings(
            [lst, lst.copy()], min_acres=2, max_price=60000,
            target_areas=[],
        )
        assert len(result) == 1

    def test_flags_target_area(self):
        listings = [_make_listing(location="Tres Piedras, NM")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=["Tres Piedras"],
        )
        assert result[0]["priority"] is True

    def test_no_flag_non_target_area(self):
        listings = [_make_listing(location="Santa Fe, NM")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=["Tres Piedras"],
        )
        assert result[0]["priority"] is False

    def test_high_priority_under_50k_with_water(self):
        listings = [_make_listing(price="$45,000", water="well")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=[],
        )
        assert result[0].get("high_priority") is True

    def test_no_high_priority_without_water(self):
        listings = [_make_listing(price="$45,000", water="none")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=[],
        )
        assert result[0].get("high_priority") is not True

    def test_sorts_priority_first(self):
        listings = [
            _make_listing(
                title="Non-priority", price="$30,000",
                location="Santa Fe, NM",
            ),
            _make_listing(
                title="Priority", price="$35,000",
                location="Tres Piedras, NM",
            ),
        ]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=["Tres Piedras"],
        )
        assert result[0]["title"] == "Priority"

    def test_populates_numeric_fields(self):
        listings = [_make_listing(price="$35,000", acres="5 acres")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=[],
        )
        assert result[0]["price_num"] == 35000
        assert result[0]["acres_num"] == 5.0

    def test_keeps_unparseable_price(self):
        """Listings with unparseable price are kept (not filtered)."""
        listings = [_make_listing(price="Call for price")]
        result = _filter_listings(
            listings, min_acres=2, max_price=60000,
            target_areas=[],
        )
        assert len(result) == 1
        assert result[0]["price_num"] is None


# --- _find_new ---

class TestFindNew:
    def test_new_listing_added_to_cache(self):
        cache = {}
        listings = [_make_listing()]
        result = _find_new(
            _filter_listings(
                listings, min_acres=0, max_price=999999,
                target_areas=[],
            ),
            cache,
        )
        assert len(result) == 1
        assert len(cache) == 1

    def test_existing_listing_skipped(self):
        listing = _make_listing()
        filtered = _filter_listings(
            [listing], min_acres=0, max_price=999999,
            target_areas=[],
        )
        cache = {}
        _find_new(filtered, cache)
        # Second call with same listing
        result = _find_new(filtered, cache)
        assert len(result) == 0


# --- _deduplicate_across_sources ---

class TestDeduplicateAcrossSources:
    def test_merges_same_listing_different_sources(self):
        a = _make_listing(source="LandFlip")
        b = _make_listing(source="Zillow")
        result = _deduplicate_across_sources([a, b])
        assert len(result) == 1
        assert "LandFlip" in result[0]["source"]
        assert "Zillow" in result[0]["source"]

    def test_keeps_different_listings(self):
        a = _make_listing(title="Parcel A", price="$30,000")
        b = _make_listing(title="Parcel B", price="$40,000")
        result = _deduplicate_across_sources([a, b])
        assert len(result) == 2

    def test_empty_input(self):
        assert _deduplicate_across_sources([]) == []


# --- _manual_links ---

class TestManualLinks:
    def test_returns_list(self):
        links = _manual_links()
        assert isinstance(links, list)
        assert len(links) >= 3

    def test_each_has_title_and_url(self):
        for link in _manual_links():
            assert "title" in link
            assert "url" in link
            assert link["url"].startswith("https://")
