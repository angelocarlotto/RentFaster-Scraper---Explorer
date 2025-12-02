# 🏠 RentFaster Scraper & Explorer

A comprehensive web scraping and data exploration tool for Canadian rental listings from RentFaster.ca. This project enables users to collect, analyze, and interactively explore rental listings across multiple cities with advanced filtering and map-based search capabilities.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Table of Contents

- [Features](#-features)
- [Demo](#-demo)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Advanced Features](#-advanced-features)
- [Configuration](#-configuration)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### Data Collection
- **Multi-City Scraping**: Scrape listings from 20+ Canadian cities across 4 provinces
- **Parallel Processing**: Fast data collection using concurrent downloads
- **Offline Scraping**: Parse pre-downloaded HTML files for efficient processing
- **Automatic Deduplication**: Remove duplicate listings across cities
- **Progress Tracking**: Real-time scraping progress with detailed logs

### Web Interface
- **Interactive Filtering**: 15+ filter options with AND/OR logic operators
- **Map-Based Search**: Click on map to find listings within a custom radius
- **Distance Sorting**: Automatically sort by proximity to selected location
- **Smart Search**: Full-text search across title, address, and descriptions
- **Saved Filters**: Save and reload custom filter combinations
- **Live Statistics**: Real-time stats on average rent, size, and availability
- **Responsive Design**: Mobile-friendly interface with optimized layouts

### Advanced Filtering
- **Price Ranges**: Filter by monthly rent brackets
- **Property Features**: Bedrooms, bathrooms, size, parking spots
- **Amenities**: Utilities included, furnished options, pet-friendly
- **Location**: City, community/neighborhood selection
- **Quick Filters**: Immediate availability, best value ($/sqft), pet-friendly
- **Carpet Type**: Filter by flooring type preferences

### Map Features
- **Interactive Map**: Leaflet-based mapping with OpenStreetMap tiles
- **Point of Interest**: Click any listing to set as location reference
- **Radius Control**: Adjustable search radius (0.5 - 20 km)
- **Distance Badges**: Visual distance indicators on each listing
- **Location Markers**: Hover over cards to preview location on map
- **Optional Radius Filter**: View all distances or filter by radius

## 🎥 Demo

![RentFaster Explorer Screenshot](docs/screenshot.png)

**Key Interface Elements:**
- Left sidebar with collapsible filter sections
- Interactive map with radius control
- Listing cards with distance badges
- Real-time result count and statistics

## 🏗 Architecture

```
┌─────────────────┐
│  RentFaster.ca  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Data Collection Pipeline       │
│  ┌──────────────────────────┐  │
│  │ 1. Download HTML Pages   │  │
│  │    (Parallel)            │  │
│  └──────────┬───────────────┘  │
│             ▼                   │
│  ┌──────────────────────────┐  │
│  │ 2. Scrape Offline        │  │
│  │    (BeautifulSoup)       │  │
│  └──────────┬───────────────┘  │
│             ▼                   │
│  ┌──────────────────────────┐  │
│  │ 3. Deduplicate & Enrich  │  │
│  │    (Python)              │  │
│  └──────────┬───────────────┘  │
└─────────────┼───────────────────┘
              ▼
     ┌────────────────┐
     │  JSON Database │
     │  (6,800+ items)│
     └────────┬───────┘
              │
              ▼
┌─────────────────────────────────┐
│  Flask Web Application          │
│  ┌──────────────────────────┐  │
│  │  Backend (Python/Flask)  │  │
│  │  - API Endpoints         │  │
│  │  - Data Enrichment       │  │
│  │  - Caching Layer         │  │
│  └──────────┬───────────────┘  │
│             ▼                   │
│  ┌──────────────────────────┐  │
│  │  Frontend (HTML/JS)      │  │
│  │  - Filters & Search      │  │
│  │  - Leaflet Map           │  │
│  │  - Distance Calculation  │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/rentfaster_scrap.git
   cd rentfaster_scrap
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the web application**
   ```bash
   python3 scripts/web_app.py
   ```

5. **Open in browser**
   ```
   http://localhost:5001
   ```

## 📖 Usage

### Running the Web Explorer

The simplest way to explore listings:

```bash
python3 scripts/web_app.py
```

Then open `http://localhost:5001` in your browser.

### Scraping Fresh Data

#### Option 1: Download + Scrape (Recommended)

```bash
# Step 1: Download raw HTML pages (parallel, fast)
python3 scripts/download_raw_html_parallel.py

# Step 2: Scrape offline from downloaded HTML
python3 scripts/scrape_offline_parallel.py

# Step 3: Deduplicate and clean data
python3 scripts/deduplicate_database.py
```

#### Option 2: Direct Scraping (Slower)

```bash
# Fetch and parse in one step
python3 scripts/fetch_listings_multi_city.py
```

### Analyzing Data

```bash
# Show statistics and insights
python3 scripts/analyze_data.py

# Quick summary
python3 scripts/show_summary.py

# Check scraping progress
bash scripts/check_progress.sh
```

## 📁 Project Structure

```
rentfaster_scrap/
├── scripts/                          # All Python scripts
│   ├── web_app.py                   # Flask web application
│   ├── download_raw_html_parallel.py # HTML downloader
│   ├── scrape_offline_parallel.py   # Offline scraper
│   ├── fetch_listings_multi_city.py # Direct scraper
│   ├── deduplicate_database.py      # Deduplication tool
│   ├── analyze_data.py              # Data analysis
│   └── show_summary.py              # Quick stats
│
├── templates/                        # HTML templates
│   └── index.html                   # Main web interface (2,978 lines)
│
├── static/                          # Static assets (CSS, JS, images)
│
├── data/                            # Data storage
│   ├── rentfaster_detailed_offline.json  # Main database
│   └── rentfaster_listings.json          # Backup
│
├── raw/                             # Downloaded HTML files
│   ├── calgary/
│   ├── edmonton/
│   └── ...
│
├── logs/                            # Scraping logs
│
├── docs/                            # Documentation
│
├── cities_config.json               # City configuration (20+ cities)
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker configuration
├── docker-compose.yml               # Docker Compose setup
└── README.md                        # This file
```

## 🎯 Advanced Features

### Map-Based Location Search

1. **Setting a Location**
   - Click anywhere on the map to set a reference point
   - OR click the "🎯 Point of Interest" button on any listing card
   - Map automatically centers and zooms to the location

2. **Radius Control**
   - Adjust the slider to change search radius (0.5 - 20 km)
   - Blue circle on map shows the search area
   - Distance badges appear on all listings (e.g., "📏 2.35 km")

3. **Optional Radius Filter**
   - **Unchecked** (default): View all listings with distances shown
   - **Checked**: Only show listings within the selected radius
   - Allows you to see how far everything is without limiting results

4. **Distance Sorting**
   - Automatically switches to distance sorting when location is set
   - Listings with distance 0.00 km appear first (same location)
   - Scroll is automatically adjusted to show closest listings

### Filter Operators

Each multi-select filter supports two logic modes:

- **OR Logic** (default): Match ANY selected option
  - Example: "1 bed OR 2 bed" shows all 1-bed AND all 2-bed units
  
- **AND Logic**: Match ALL selected options (union)
  - Example: Cities "Calgary AND Edmonton" shows listings from both cities
  - Useful for combining multiple locations or communities

### Saved Filters

1. **Save Current Filter**
   - Configure your desired filters
   - Enter a name in the "Save Current Filter" field
   - Click "💾 Salvar" to save

2. **Load Saved Filter**
   - Select from the dropdown
   - Click "📂 Carregar" to apply
   - All filters, operators, and settings are restored

3. **Delete Saved Filter**
   - Select from dropdown
   - Click "🗑️ Deletar" to remove

Filters are stored in browser's localStorage (persistent across sessions).

### Cost Analysis

The interface calculates and displays:
- **Average Rent**: Mean monthly rent across all listings
- **Average Size**: Mean square footage
- **$/sq ft**: Cost efficiency metric
- **Best Value Filter**: Quick filter for listings under $1.50/sqft

## ⚙️ Configuration

### City Configuration

Edit `cities_config.json` to enable/disable cities:

```json
{
  "cities": [
    {
      "name": "Calgary",
      "province": "Alberta",
      "province_code": "ab",
      "city_code": "calgary",
      "city_id": 1,
      "url": "https://www.rentfaster.ca/ab/calgary/",
      "enabled": true,
      "priority": 1
    }
  ]
}
```

### Web App Configuration

Edit `scripts/web_app.py` to customize:

```python
# Port
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

# Data source
LISTINGS_JSON = os.path.join(data_dir, 'rentfaster_detailed_offline.json')
```

### Map Configuration

Edit `templates/index.html` to customize map:

```javascript
// Default center (Calgary)
map = L.map('map').setView([51.0447, -114.0719], 11);

// Default radius
let selectedRadius = 5; // km

// Radius range
<input type="range" id="radius-slider" min="0.5" max="20" step="0.5" value="5">
```

## 🔧 Development

### Running in Development Mode

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with auto-reload
python3 scripts/web_app.py
# Flask debug mode is enabled by default
```

### Docker Deployment

```bash
# Build and run
docker-compose up --build

# Access at http://localhost:5001
```

### Code Structure

**Backend (Flask)**
- `web_app.py`: Main Flask application
- Routes: `/` (main page), `/api/listings` (JSON API)
- Data enrichment: Price parsing, sqft calculation, cost per sqft
- Caching: Automatic reload when JSON file changes

**Frontend (JavaScript)**
- `templates/index.html`: Single-page application
- Leaflet.js: Map integration
- Vanilla JavaScript: No framework dependencies
- Real-time filtering: Debounced for performance

### Key Algorithms

**Distance Calculation (Haversine Formula)**
```javascript
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c; // Distance in km
}
```

**Sorting with Nullish Coalescing**
```javascript
// Handles distance = 0 correctly (0 is falsy but valid)
const distA = a._distance ?? 999999;
const distB = b._distance ?? 999999;
return distA - distB;
```

## 🐛 Troubleshooting

### Common Issues

**Problem**: "No listings found"
- **Solution**: Run scraping scripts to populate data
- Check if `data/rentfaster_detailed_offline.json` exists
- Verify file is not empty (should be ~50MB with 6,800+ listings)

**Problem**: Map not loading
- **Solution**: Check internet connection (uses OpenStreetMap tiles)
- Clear browser cache
- Check browser console for JavaScript errors

**Problem**: Distance sorting not working
- **Solution**: Ensure coordinates exist in listing data
- Click "Point of Interest" button or map to set location
- Check browser console for calculation errors

**Problem**: Filters not applying
- **Solution**: Clear all filters and try again
- Check if "Active Filters" badge shows correct count
- Refresh page to reset state

**Problem**: Import errors when running scripts
- **Solution**: Activate virtual environment: `source .venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Performance Tips

- **Large datasets**: First 50 listings shown by default
- **Slow filtering**: Uses debounced search (150ms delay)
- **Memory usage**: Caching prevents reloading data on every request
- **Map rendering**: Markers only created on hover (lazy loading)

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit your changes**
   ```bash
   git commit -m 'Add amazing feature'
   ```
4. **Push to the branch**
   ```bash
   git push origin feature/amazing-feature
   ```
5. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Add comments for complex logic
- Test all features before submitting PR
- Update README.md if adding new features
- Keep commits atomic and descriptive

### Areas for Contribution

#### Planned Improvements
- [ ] **Remove debug logging**: Clean up console.log statements from production code
- [ ] **Internationalization (i18n)**: Add multi-language support (English, Portuguese, French)
- [ ] **Code refactoring**: Modularize JavaScript code into separate files
  - [ ] Split filters logic into `filters.js`
  - [ ] Extract map functionality to `map.js`
  - [ ] Create utility functions in `utils.js`
  - [ ] Separate API calls into `api.js`
- [ ] **Backend modularization**: Break Flask app into blueprints
- [ ] **Configuration management**: Move hardcoded values to config files
- [ ] **Unit tests**: Add test coverage for critical functions
- [ ] **Error handling**: Improve error messages and user feedback

#### Feature Enhancements
- [ ] Add more Canadian cities
- [ ] Implement user authentication
- [ ] Add favorite/bookmark functionality
- [ ] Create mobile app
- [ ] Add email alerts for new listings
- [ ] Improve data visualization (charts, graphs)
- [ ] Add price prediction ML model
- [ ] Optimize scraping performance
- [ ] Add export functionality (CSV, PDF)
- [ ] Implement API rate limiting
- [ ] Add dark mode theme
- [ ] Implement listing comparison feature
- [ ] Add historical price trends
- [ ] Create shareable filter links

## 📊 Data Statistics

Current dataset (as of December 2025):
- **Total Listings**: 6,800+
- **Cities Covered**: 20+ (Calgary, Edmonton, Regina, Saskatoon, etc.)
- **Provinces**: Alberta, Saskatchewan, Manitoba, British Columbia
- **Data Points**: ~30 fields per listing
- **Average Update Frequency**: Daily (manual scraping)
- **Database Size**: ~50 MB (JSON format)

### Listing Data Schema

Each listing contains:
```json
{
  "title": "2 Bedroom Apartment",
  "price": "1500",
  "beds": "2",
  "baths": "1",
  "sq_feet": "850",
  "address": "123 Main St SW",
  "community": "Downtown",
  "city": "Calgary",
  "latitude": "51.0447",
  "longitude": "-114.0719",
  "immediately_available": "Yes",
  "pet_friendly": "No",
  "utilities_included": ["Heat", "Water"],
  "amenities": ["Parking", "Laundry"],
  "furnished": "No",
  "parking_spots": "1",
  "date": "2024-12-01",
  "link": "https://...",
  "intro": "...",
  "full_description": "..."
}
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **RentFaster.ca**: Source of rental listing data
- **Leaflet**: Interactive mapping library
- **OpenStreetMap**: Map tiles and data
- **Flask**: Web framework
- **BeautifulSoup**: HTML parsing
- **Community**: Thanks to all contributors

## 📧 Contact

For questions, suggestions, or issues:
- Open an issue on GitHub
- Email: your.email@example.com
- Twitter: @yourhandle

---

**⭐ Star this repo if you find it useful!**

**🍴 Fork it to create your own version!**

**📢 Share it with others looking for rental data tools!**

---

*Last updated: December 1, 2025*
