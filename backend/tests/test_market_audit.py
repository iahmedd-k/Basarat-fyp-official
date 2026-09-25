"""Comprehensive Audit and Live Validation for Market Overview and Indices Module.

Validates:
1. Market Indices & Constituents:
   - GET /market/indices (KSE100, KSE30, KMI30 and other active indices)
   - GET /market/indices/kse-100 (KSE-100 constituent list & freshness)
   - GET /market/indices/kse-30 (KSE-30 constituent list & freshness)
   - GET /market/indices/kmi-30 (KMI-30 Shariah compliant constituent list & freshness)
2. Sector Performance:
   - GET /market/sectors/performance (Order: asc/desc, average change %, sector breakdown)
3. Market Breadth & Movers:
   - GET /market/gainers (Top gainers with limit parameter)
   - GET /market/losers (Top losers with limit parameter)
   - GET /market/volume-spikes (High volume stocks with limit parameter)
   - GET /market/sentiment-overview (Advancing/declining ratio, market mood)
4. Comprehensive Quotes & Search Filtering:
   - GET /market/quotes & GET /market/all-stocks (Full ~500 PSX market quotes)
   - Comma-separated symbol filtering (e.g. symbols=OGDC,PPL,SYS)
   - Sector filtering (e.g. sector=Commercial Banks)
   - Search keyword (e.g. search=cement)
   - Multi-field sorting (sort_by=volume, change_pct, current, ldcp, symbol with order=asc/desc)
   - Pagination (limit & offset)
5. Validation Error Boundaries:
   - 422 Validation Error on invalid sort_by or order parameters
"""

import sys
from pathlib import Path
import httpx

# Setup python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_market_audit():
    print("\n" + "="*70)
    print(" LIVE AWS END-TO-END AUDIT: MARKET OVERVIEW & INDICES")
    print("="*70)

    base_url = "http://16.16.26.247:8000/api/v1"
    with httpx.Client(base_url=base_url, timeout=35.0) as client:
        # -------------------------------------------------------------
        # 1. Market Indices & Constituents
        # -------------------------------------------------------------
        print("\n--- 1. Testing Market Indices (/market/indices) ---")
        r_ind = client.get("/market/indices")
        assert r_ind.status_code == 200, f"Failed /market/indices: {r_ind.text}"
        ind_data = r_ind.json()
        assert "indices" in ind_data
        print(f" [PASS] GET /market/indices -> Status 200 | Count: {len(ind_data['indices'])}")
        for idx in ind_data["indices"][:3]:
            print(f"        Index: {idx.get('name')} ({idx.get('code')}) | Value: {idx.get('value')} | Change: {idx.get('change_pct')}%")

        # KSE-100 Constituents
        r_kse100 = client.get("/market/indices/kse-100")
        assert r_kse100.status_code == 200
        kse100_data = r_kse100.json()
        assert kse100_data["code"] == "KSE100"
        assert len(kse100_data["constituents"]) > 0
        print(f" [PASS] GET /market/indices/kse-100 -> Status 200 | Constituents: {len(kse100_data['constituents'])}")

        # KSE-30 Constituents
        r_kse30 = client.get("/market/indices/kse-30")
        assert r_kse30.status_code == 200
        kse30_data = r_kse30.json()
        assert kse30_data["code"] == "KSE30"
        print(f" [PASS] GET /market/indices/kse-30 -> Status 200 | Constituents: {len(kse30_data['constituents'])}")

        # KMI-30 Constituents
        r_kmi30 = client.get("/market/indices/kmi-30")
        assert r_kmi30.status_code == 200
        kmi30_data = r_kmi30.json()
        assert kmi30_data["code"] == "KMI30"
        assert kmi30_data.get("shariah_compliant") is True
        print(f" [PASS] GET /market/indices/kmi-30 -> Status 200 | Shariah Compliant: True | Constituents: {len(kmi30_data['constituents'])}")

        # -------------------------------------------------------------
        # 2. Sector Performance
        # -------------------------------------------------------------
        print("\n--- 2. Testing Sector Performance (/market/sectors/performance) ---")
        r_sec_desc = client.get("/market/sectors/performance?order=desc")
        assert r_sec_desc.status_code == 200
        sec_data = r_sec_desc.json()
        assert "sectors" in sec_data
        print(f" [PASS] GET /market/sectors/performance?order=desc -> Status 200 | Sectors Count: {len(sec_data['sectors'])}")
        if sec_data["sectors"]:
            top_sec = sec_data["sectors"][0]
            print(f"        Top Sector: {top_sec.get('name')} | Avg Change: {top_sec.get('avg_change_pct')}% | Stock Count: {top_sec.get('stock_count')}")

        r_sec_asc = client.get("/market/sectors/performance?order=asc")
        assert r_sec_asc.status_code == 200
        print(f" [PASS] GET /market/sectors/performance?order=asc -> Status 200")

        # -------------------------------------------------------------
        # 3. Market Breadth & Movers
        # -------------------------------------------------------------
        print("\n--- 3. Testing Gainers, Losers, Volume Spikes & Sentiment Overview ---")
        
        # Gainers
        r_gainers = client.get("/market/gainers?limit=5")
        assert r_gainers.status_code == 200
        gainers_data = r_gainers.json()
        assert len(gainers_data.get("gainers", [])) <= 5
        print(f" [PASS] GET /market/gainers?limit=5 -> Status 200 | Returned: {len(gainers_data.get('gainers', []))}")
        if gainers_data.get("gainers"):
            top_g = gainers_data["gainers"][0]
            print(f"        Top Gainer: {top_g.get('symbol')} (+{top_g.get('change_pct')}%) | Current: PKR {top_g.get('current')}")

        # Losers
        r_losers = client.get("/market/losers?limit=5")
        assert r_losers.status_code == 200
        losers_data = r_losers.json()
        print(f" [PASS] GET /market/losers?limit=5 -> Status 200 | Returned: {len(losers_data.get('losers', []))}")

        # Volume Spikes
        r_spikes = client.get("/market/volume-spikes?limit=5")
        assert r_spikes.status_code == 200
        spikes_data = r_spikes.json()
        print(f" [PASS] GET /market/volume-spikes?limit=5 -> Status 200 | Returned: {len(spikes_data.get('volume_spikes', []))}")
        if spikes_data.get("volume_spikes"):
            top_v = spikes_data["volume_spikes"][0]
            print(f"        Top Volume: {top_v.get('symbol')} | Volume: {top_v.get('volume'):,} shares")

        # Sentiment Overview
        r_sent = client.get("/market/sentiment-overview")
        assert r_sent.status_code == 200
        sent_data = r_sent.json()
        print(f" [PASS] GET /market/sentiment-overview -> Status 200 | Market Mood: '{sent_data.get('market_mood')}' | Advancing: {sent_data.get('advancing')} | Declining: {sent_data.get('declining')} | A/D Ratio: {sent_data.get('advance_decline_ratio')}")

        # -------------------------------------------------------------
        # 4. Quotes & Advanced Filtering
        # -------------------------------------------------------------
        print("\n--- 4. Testing Market Quotes & Full Stock Directory (/market/quotes) ---")
        
        # 4.1 General quotes
        r_quotes = client.get("/market/quotes?limit=15&offset=0")
        assert r_quotes.status_code == 200
        q_data = r_quotes.json()
        assert len(q_data["stocks"]) == 15
        assert q_data["total"] >= 15
        print(f" [PASS] GET /market/quotes?limit=15 -> Status 200 | Total Market Stocks: {q_data['total']} | Page Count: {len(q_data['stocks'])}")

        # 4.2 Symbols Filter
        r_syms = client.get("/market/quotes?symbols=OGDC,PPL,SYS,LUCK")
        assert r_syms.status_code == 200
        syms_data = r_syms.json()
        assert syms_data["filtered"] is True
        assert len(syms_data["stocks"]) <= 4
        matched_symbols = [s["symbol"] for s in syms_data["stocks"]]
        print(f" [PASS] GET /market/quotes?symbols=OGDC,PPL,SYS,LUCK -> Status 200 | Matched: {matched_symbols}")

        # 4.3 Sector Filter
        r_sec_filt = client.get("/market/quotes?sector=Commercial Banks&limit=5")
        assert r_sec_filt.status_code == 200
        sec_filt_data = r_sec_filt.json()
        assert sec_filt_data["filtered"] is True
        print(f" [PASS] GET /market/quotes?sector=Commercial Banks -> Status 200 | Found: {sec_filt_data['total']}")

        # 4.4 Search Keyword
        r_search = client.get("/market/quotes?search=cement&limit=5")
        assert r_search.status_code == 200
        search_data = r_search.json()
        assert search_data["filtered"] is True
        print(f" [PASS] GET /market/quotes?search=cement -> Status 200 | Found: {search_data['total']}")

        # 4.5 Multi-field Sorting
        for sort_field in ["volume", "change_pct", "current", "ldcp", "symbol"]:
            r_sort = client.get(f"/market/quotes?limit=5&sort_by={sort_field}&order=desc")
            assert r_sort.status_code == 200
            print(f" [PASS] GET /market/quotes?sort_by={sort_field}&order=desc -> Status 200")

        # 4.6 Alias Endpoint
        r_alias = client.get("/market/all-stocks?limit=5")
        assert r_alias.status_code == 200
        print(f" [PASS] GET /market/all-stocks?limit=5 (Alias Endpoint) -> Status 200")

        # -------------------------------------------------------------
        # 5. Validation Rejections (422)
        # -------------------------------------------------------------
        print("\n--- 5. Testing Error Boundaries (422 Rejections) ---")
        r_bad_sort = client.get("/market/quotes?sort_by=INVALID_FIELD")
        print(f" GET /market/quotes?sort_by=INVALID_FIELD -> Status {r_bad_sort.status_code}")
        assert r_bad_sort.status_code == 422

        r_bad_order = client.get("/market/quotes?order=SIDEWAYS")
        print(f" GET /market/quotes?order=SIDEWAYS -> Status {r_bad_order.status_code}")
        assert r_bad_order.status_code == 422
        print(" [PASS] 422 Validation Error handling verified.")


if __name__ == "__main__":
    run_market_audit()
    print("\n" + "="*70)
    print(" ALL MARKET OVERVIEW & INDICES AUDIT TESTS PASSED!")
    print("="*70 + "\n")
