"""Tests for vehicle_tracker.py pure helper functions."""

import hashlib

import pytest

from vehicle_tracker import (
    _filter_listings,
    _is_long_bed,
    _listing_id,
    _parse_miles,
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

    def test_below_range(self):
        assert _parse_price("$5,000") is None

    def test_above_range(self):
        assert _parse_price("$100,000") is None

    def test_boundary_low_exclusive(self):
        """10000 is excluded (condition is 10000 < v)."""
        assert _parse_price("$10,000") is None

    def test_boundary_low_just_above(self):
        assert _parse_price("$10,001") == 10001

    def test_boundary_high_just_below(self):
        assert _parse_price("$99,999") == 99999

    def test_empty_string(self):
        assert _parse_price("") is None

    def test_none(self):
        assert _parse_price(None) is None

    def test_no_digits(self):
        assert _parse_price("no price listed") is None


# --- _parse_miles ---

class TestParseMiles:
    def test_with_commas(self):
        assert _parse_miles("45,000 mi") == 45000

    def test_plain_number(self):
        assert _parse_miles("32000") == 32000

    def test_zero_excluded(self):
        """0 is excluded (condition is 0 < v)."""
        assert _parse_miles("0") is None

    def test_one_mile(self):
        assert _parse_miles("1") == 1

    def test_boundary_high_just_below(self):
        assert _parse_miles("499,999") == 499999

    def test_boundary_high_excluded(self):
        assert _parse_miles("500,000") is None

    def test_empty_string(self):
        assert _parse_miles("") is None

    def test_none(self):
        assert _parse_miles(None) is None

    def test_no_digits(self):
        assert _parse_miles("unknown") is None


# --- _is_long_bed ---

class TestIsLongBed:
    @pytest.mark.parametrize("title", [
        "Tacoma TRD Off-Road LB",
        "Tacoma Long Bed 4WD",
        "Tacoma 6 ft bed",
        "Tacoma 6' bed",
        "Tacoma 6-ft bed",
        "6 Bed Tacoma",
        "6-foot bed Tacoma",
    ])
    def test_detects_keywords(self, title):
        assert _is_long_bed(title) is True

    def test_no_keyword(self):
        assert _is_long_bed("Tacoma TRD Sport Double Cab") is False

    def test_case_insensitive(self):
        assert _is_long_bed("tacoma long bed 4wd") is True

    def test_empty_string(self):
        assert _is_long_bed("") is False

    def test_none(self):
        assert _is_long_bed(None) is False


# --- _listing_id ---

class TestListingId:
    def test_deterministic(self):
        listing = {"title": "Tacoma", "price": "35000", "miles": "40000", "location": "Denver"}
        assert _listing_id(listing) == _listing_id(listing)

    def test_different_price_different_hash(self):
        a = {"title": "Tacoma", "price": "35000", "miles": "40000", "location": "Denver"}
        b = {"title": "Tacoma", "price": "36000", "miles": "40000", "location": "Denver"}
        assert _listing_id(a) != _listing_id(b)

    def test_missing_keys(self):
        """Missing keys default to empty string, still produces a hash."""
        result = _listing_id({})
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hex digest

    def test_known_hash(self):
        listing = {"title": "T", "price": "1", "miles": "2", "location": "X"}
        expected = hashlib.md5(b"T-1-2-X").hexdigest()
        assert _listing_id(listing) == expected


# --- _filter_listings ---

def _make_listing(title="Tacoma 4WD", price="35000", miles="40000",
                  location="Denver", url="", source="Test"):
    return {
        "title": title, "price": price, "miles": miles,
        "location": location, "url": url, "source": source,
    }


class TestFilterListings:
    def test_filters_over_max_price(self):
        listings = [_make_listing(price="$50,000")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert len(result) == 0

    def test_keeps_under_max_price(self):
        listings = [_make_listing(price="$35,000")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert len(result) == 1

    def test_filters_over_max_miles(self):
        listings = [_make_listing(miles="80,000")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert len(result) == 0

    def test_deduplicates(self):
        lst = _make_listing()
        result = _filter_listings([lst, lst.copy()], max_price=40000, max_miles=60000)
        assert len(result) == 1

    def test_sorts_by_price_ascending(self):
        listings = [
            _make_listing(price="$39,000", miles="30000"),
            _make_listing(price="$25,000", miles="30001"),
            _make_listing(price="$35,000", miles="30002"),
        ]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        prices = [r["price_num"] for r in result]
        assert prices == [25000, 35000, 39000]

    def test_adds_verify_4wd_note(self):
        listings = [_make_listing(title="Tacoma TRD Sport")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert result[0].get("note") == "verify 4WD"

    def test_no_4wd_note_when_present(self):
        listings = [_make_listing(title="Tacoma 4WD TRD")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert "note" not in result[0]

    def test_adds_long_bed_field(self):
        listings = [_make_listing(title="Tacoma Long Bed 4WD")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert "Long Bed" in result[0]["bed"]

    def test_adds_verify_bed_field(self):
        listings = [_make_listing(title="Tacoma 4WD TRD")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert "Verify" in result[0]["bed"]

    def test_populates_numeric_fields(self):
        listings = [_make_listing(price="$35,000", miles="40,000")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert result[0]["price_num"] == 35000
        assert result[0]["miles_num"] == 40000

    def test_empty_input(self):
        assert _filter_listings([], max_price=40000, max_miles=60000) == []

    def test_unparseable_price_passes_through(self):
        """Listings with unparseable price are not filtered out."""
        listings = [_make_listing(price="Call for price", miles="40000")]
        result = _filter_listings(listings, max_price=40000, max_miles=60000)
        assert len(result) == 1
        assert result[0]["price_num"] is None
