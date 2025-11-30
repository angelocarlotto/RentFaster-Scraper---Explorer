# RentFaster Scraping Workflow

## Overview

This project now has a **two-stage scraping process**:

1. **Download Stage**: Download raw HTML files from RentFaster.ca
2. **Extraction Stage**: Parse local HTML files to extract data (offline)

This approach is **much faster** and **avoids Cloudflare issues** because you only need to bypass Cloudflare once during download, then you can parse the data offline as many times as needed.

---

## Stage 1: Download Raw HTML

### Script: `download_raw_html_parallel.py`

Downloads raw HTML files for all listings and saves them to the `raw/` directory.

**Usage:**
```bash
# Download all listings with 5 workers
python3 download_raw_html_parallel.py all 5 true

# Download first 100 listings (test)
python3 download_raw_html_parallel.py 100 5 true

# Download remaining listings (skips already downloaded)
python3 download_raw_html_parallel.py all 10 true
```

**Parameters:**
- `num_listings`: Number to download (or `all`/`0` for all)
- `num_workers`: Parallel Chrome instances (recommended: 5-10)
- `headless`: `true` for background, `false` for visible browsers

**Features:**
- ✅ Parallel downloading with multiple Chrome instances
- ✅ Cloudflare bypass with random delays (3-7 seconds)
- ✅ Auto-skip already downloaded files
- ✅ Saves HTML + metadata JSON for each listing
- ✅ Live progress display

**Output:**
```
raw/
├── 693407.html
├── 693407.json
├── 567436.html
├── 567436.json
└── ...
```

---

## Stage 2: Extract Data from Local HTML

### Script: `scrape_offline_parallel.py`

Parses the downloaded HTML files and extracts all data (parking, descriptions, amenities, etc.)

**Usage:**
```bash
# Scrape all downloaded HTML files with 10 workers
python3 scrape_offline_parallel.py 10

# Scrape with 20 workers (faster)
python3 scrape_offline_parallel.py 20
```

**Parameters:**
- `num_workers`: Parallel CPU workers (recommended: 10-20)

**Features:**
- ✅ **SUPER FAST** - No network delays, pure CPU processing
- ✅ Parse HTML with BeautifulSoup
- ✅ Extract parking spots with improved patterns
- ✅ Extract full descriptions
- ✅ Extract utilities, amenities, furnished status
- ✅ Can re-run as many times as needed to refine extraction

**Output:**
- `rentfaster_detailed_offline.json` - Complete database with all extracted data

---

## Current Workflow (Two-Stage Architecture)

### Stage 1: Download HTML (One Time)
```
download_raw_html_parallel.py → raw/calgary/*.html files
         (6,867 listings with 40 workers = ~2-4 hours)
```

### Stage 2: Parse Offline (Unlimited Iterations)
```
scrape_offline_parallel.py → rentfaster_detailed_offline.json
         (2,376 files × 20 workers = ~1-2 minutes)
```

**Advantages:**
- ✅ Fast offline parsing (50-100x faster than online)
- ✅ No Cloudflare issues during development
- ✅ Can refine extraction logic without re-downloading
- ✅ Network-independent after initial download

### New Workflow (Download + Offline)
```
Step 1: download_raw_html_parallel.py → raw/*.html (7,500 × 8 sec = 17 hours)
Step 2: scrape_offline_parallel.py → rentfaster_detailed_offline.json (7,500 × 0.02 sec = 2.5 minutes)
```

**Advantages:**
- ✅ Download once, parse many times
- ✅ Offline parsing is 400x faster (2.5 min vs 17 hours)
- ✅ Can refine extraction logic and re-run instantly
- ✅ No network errors during parsing
- ✅ Can distribute raw HTML to other machines

---

## Complete Workflow Example

### Initial Setup
```bash
# 1. Download all raw HTML files (do this ONCE)
python3 download_raw_html_parallel.py all 10 true

# This will take ~17 hours for 7,500 listings
# But you only need to do it once!
```

### Extract Data (Can repeat many times)
```bash
# 2. Extract data from downloaded HTML files
python3 scrape_offline_parallel.py 20

# This takes only ~2-5 minutes!
# Output: rentfaster_detailed_offline.json
```

### Update Extraction Logic
```bash
# If you want to improve parking extraction:
# 1. Edit scrape_offline_parallel.py (update regex patterns)
# 2. Re-run offline scraper (only 2-5 minutes!)
python3 scrape_offline_parallel.py 20

# No need to re-download HTML!
```

---

## File Structure

```
rentfaster_scrap/
├── download_raw_html_parallel.py     # Stage 1: Download HTML
├── scrape_offline_parallel.py        # Stage 2: Parse HTML offline
├── web_app.py                        # Flask web interface
├── deduplicate_database.py           # Remove duplicate listings
├── show_summary.py                   # Display data statistics
├── analyze_data.py                   # Comprehensive data analysis
├── investigate_prices.py             # Price anomaly investigation
├── rescrape_single.py                # Re-scrape single listing
├── rentfaster_listings.json          # Basic listings (legacy)
├── rentfaster_detailed_offline.json  # Full database (current)
└── raw/                              # Downloaded HTML files
    └── calgary/
        ├── 693407.html
        ├── 567436.html
        └── ...
```

---

## Tips

### Incremental Downloads
The downloader automatically skips already-downloaded files, so you can run it multiple times:

```bash
# Download first 1000 (test run)
python3 download_raw_html_parallel.py 1000 10 true

# Later: download the rest
python3 download_raw_html_parallel.py all 10 true
# (automatically skips the first 1000)
```

### Adjust for Cloudflare
If you're getting blocked by Cloudflare, reduce workers:

```bash
# Slower but less likely to trigger Cloudflare
python3 download_raw_html_parallel.py all 3 true
```

### Refine Extraction
The offline scraper is so fast you can iterate quickly:

```bash
# Edit scrape_offline_parallel.py
# Run: python3 scrape_offline_parallel.py 20
# Check results
# Repeat!
```

---

## Performance Comparison

| Task | Old Method | New Method | Improvement |
|------|-----------|-----------|-------------|
| Initial scrape | 17-21 hours | 17 hours download + 2 min parse | Similar |
| Re-scrape for improvements | 17-21 hours | 2 minutes | **500x faster!** |
| Parking extraction rate | 20.7% | Will test | TBD |
| Network errors | High impact | Only affects download | More stable |

---

## Next Steps

1. Run `download_raw_html_parallel.py` to download all HTML files
2. Run `scrape_offline_parallel.py` to extract data
3. Update `web_app.py` to use `rentfaster_detailed_offline.json`
4. Enjoy fast iteration on extraction logic! 🚀
