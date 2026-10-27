"""
Country code mappings and related utilities.

This module contains ISO country code mappings used for data normalization
and geographic visualizations.
"""

# =============================================================================
# ISO3 to ISO2 Country Code Mapping
# =============================================================================

ISO3_TO_ISO2 = {
    "ABW": "AW", "AFG": "AF", "AGO": "AO", "ALB": "AL", "AND": "AD", "ARE": "AE",
    "ARG": "AR", "ARM": "AM", "AUS": "AU", "AUT": "AT", "AZE": "AZ", "BDI": "BI",
    "BEL": "BE", "BEN": "BJ", "BFA": "BF", "BGD": "BD", "BGR": "BG", "BHR": "BH",
    "BHS": "BS", "BIH": "BA", "BLR": "BY", "BLZ": "BZ", "BOL": "BO", "BRA": "BR",
    "BRB": "BB", "BRN": "BN", "BTN": "BT", "BWA": "BW", "CAF": "CF", "CAN": "CA",
    "CHE": "CH", "CHL": "CL", "CHN": "CN", "CIV": "CI", "CMR": "CM", "COD": "CD",
    "COG": "CG", "COL": "CO", "COM": "KM", "CPV": "CV", "CRI": "CR", "CUB": "CU",
    "CYP": "CY", "CZE": "CZ", "DEU": "DE", "DJI": "DJ", "DNK": "DK", "DOM": "DO",
    "DZA": "DZ", "ECU": "EC", "EGY": "EG", "ERI": "ER", "ESP": "ES", "EST": "EE",
    "ETH": "ET", "FIN": "FI", "FJI": "FJ", "FRA": "FR", "FRO": "FO", "GAB": "GA",
    "GBR": "GB", "GEO": "GE", "GHA": "GH", "GIN": "GN", "GMB": "GM", "GNB": "GW",
    "GNQ": "GQ", "GRC": "GR", "GRL": "GL", "GTM": "GT", "GUY": "GY", "HKG": "HK",
    "HND": "HN", "HRV": "HR", "HTI": "HT", "HUN": "HU", "IDN": "ID", "IND": "IN",
    "IRL": "IE", "IRN": "IR", "IRQ": "IQ", "ISL": "IS", "ISR": "IL", "ITA": "IT",
    "JAM": "JM", "JOR": "JO", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KGZ": "KG",
    "KHM": "KH", "KOR": "KR", "KWT": "KW", "LAO": "LA", "LBN": "LB", "LBR": "LR",
    "LBY": "LY", "LKA": "LK", "LSO": "LS", "LTU": "LT", "LUX": "LU", "LVA": "LV",
    "MAC": "MO", "MAR": "MA", "MDA": "MD", "MDG": "MG", "MDV": "MV", "MEX": "MX",
    "MKD": "MK", "MLI": "ML", "MLT": "MT", "MMR": "MM", "MNE": "ME", "MNG": "MN",
    "MOZ": "MZ", "MRT": "MR", "MUS": "MU", "MWI": "MW", "MYS": "MY", "NAM": "NA",
    "NER": "NE", "NGA": "NG", "NIC": "NI", "NLD": "NL", "NOR": "NO", "NPL": "NP",
    "NZL": "NZ", "OMN": "OM", "PAK": "PK", "PAN": "PA", "PER": "PE", "PHL": "PH",
    "PNG": "PG", "POL": "PL", "PRI": "PR", "PRK": "KP", "PRT": "PT", "PRY": "PY",
    "PSE": "PS", "QAT": "QA", "ROU": "RO", "RUS": "RU", "RWA": "RW", "SAU": "SA",
    "SDN": "SD", "SEN": "SN", "SGP": "SG", "SLB": "SB", "SLE": "SL", "SLV": "SV",
    "SOM": "SO", "SRB": "RS", "SSD": "SS", "SUR": "SR", "SVK": "SK", "SVN": "SI",
    "SWE": "SE", "SWZ": "SZ", "SYR": "SY", "TCD": "TD", "TGO": "TG", "THA": "TH",
    "TJK": "TJ", "TKM": "TM", "TLS": "TL", "TTO": "TT", "TUN": "TN", "TUR": "TR",
    "TWN": "TW", "TZA": "TZ", "UGA": "UG", "UKR": "UA", "URY": "UY", "USA": "US",
    "UZB": "UZ", "VEN": "VE", "VNM": "VN", "YEM": "YE", "ZAF": "ZA", "ZMB": "ZM",
    "ZWE": "ZW", "XKX": "XK"
}

# Reverse mapping: ISO2 to ISO3
ISO2_TO_ISO3 = {v: k for k, v in ISO3_TO_ISO2.items()}


# =============================================================================
# Continent Bounding Boxes for Map Visualizations
# =============================================================================

CONTINENT_BOUNDS = {
    'Europe': [-25, 45, 35, 72],          # [lon_min, lon_max, lat_min, lat_max]
    'Asia': [25, 180, -10, 75],
    'North America': [-170, -50, 10, 85],
    'South America': [-90, -30, -60, 15],
    'Africa': [-20, 55, -40, 40],
    'Oceania': [100, 180, -50, 10],
    'World': [-180, 180, -60, 90],
}


# =============================================================================
# Helper Functions
# =============================================================================

def convert_iso3_to_iso2(iso3_code: str) -> str:
    """
    Convert ISO3 country code to ISO2.
    
    Args:
        iso3_code: Three-letter country code.
        
    Returns:
        Two-letter country code or None if not found.
    """
    return ISO3_TO_ISO2.get(iso3_code.upper())


def convert_iso2_to_iso3(iso2_code: str) -> str:
    """
    Convert ISO2 country code to ISO3.
    
    Args:
        iso2_code: Two-letter country code.
        
    Returns:
        Three-letter country code or None if not found.
    """
    return ISO2_TO_ISO3.get(iso2_code.upper())


def get_continent_bounds(continent: str) -> list:
    """
    Get bounding box coordinates for a continent.
    
    Args:
        continent: Continent name.
        
    Returns:
        List of [lon_min, lon_max, lat_min, lat_max] or World bounds if not found.
    """
    return CONTINENT_BOUNDS.get(continent, CONTINENT_BOUNDS['World'])


# =============================================================================
# Country Name Mappings and Normalization
# =============================================================================

COUNTRY_NAME_VARIANTS = {
    "USA": "USA",
    "United States": "USA",
    "United States of America": "USA",
    "US": "USA",
    "Russia": "RUS",
    "Russian Federation": "RUS",
    "China": "CHN",
    "People's Republic of China": "CHN",
    "India": "IND",
    "Brazil": "BRA",
    "Germany": "DEU",
    "France": "FRA",
    "United Kingdom": "GBR",
    "UK": "GBR",
    "Japan": "JPN",
    "South Korea": "KOR",
    "Korea": "KOR",
    "Mexico": "MEX",
    "Canada": "CAN",
    "Australia": "AUS",
    "Spain": "ESP",
    "Italy": "ITA",
    "Netherlands": "NLD",
    "Belgium": "BEL",
    "Poland": "POL",
    "Greece": "GRC",
    "Portugal": "PRT",
    "Turkey": "TUR",
    "South Africa": "ZAF",
    "Saudi Arabia": "SAU",
    "UAE": "ARE",
    "United Arab Emirates": "ARE",
    "Thailand": "THA",
    "Malaysia": "MYS",
    "Singapore": "SGP",
    "Indonesia": "IDN",
    "Philippines": "PHL",
    "Vietnam": "VNM",
    "Pakistan": "PAK",
    "Bangladesh": "BGD",
    "Iran": "IRN",
    "Israel": "ISR",

    # Africa
    "Algeria": "DZA",
    "Angola": "AGO",
    "Benin": "BEN",
    "Botswana": "BWA",
    "Burkina Faso": "BFA",
    "Burundi": "BDI",
    "Cabo Verde": "CPV",
    "Cape Verde": "CPV",
    "Cameroon": "CMR",
    "Central African Republic": "CAF",
    "Chad": "TCD",
    "Comoros": "COM",
    "Democratic Republic of the Congo": "COD",
    "DR Congo": "COD",
    "Congo-Kinshasa": "COD",
    "Republic of the Congo": "COG",
    "Congo": "COG",
    "Congo-Brazzaville": "COG",
    "Djibouti": "DJI",
    "Egypt": "EGY",
    "Equatorial Guinea": "GNQ",
    "Eritrea": "ERI",
    "Eswatini": "SWZ",
    "Swaziland": "SWZ",
    "Ethiopia": "ETH",
    "Gabon": "GAB",
    "Gambia": "GMB",
    "The Gambia": "GMB",
    "Ghana": "GHA",
    "Guinea": "GIN",
    "Guinea-Bissau": "GNB",
    "Ivory Coast": "CIV",
    "Côte d'Ivoire": "CIV",
    "Kenya": "KEN",
    "Lesotho": "LSO",
    "Liberia": "LBR",
    "Libya": "LBY",
    "Madagascar": "MDG",
    "Malawi": "MWI",
    "Mali": "MLI",
    "Mauritania": "MRT",
    "Mauritius": "MUS",
    "Morocco": "MAR",
    "Mozambique": "MOZ",
    "Namibia": "NAM",
    "Niger": "NER",
    "Nigeria": "NGA",
    "Rwanda": "RWA",
    "Sao Tome and Principe": "STP",
    "São Tomé and Príncipe": "STP",
    "Senegal": "SEN",
    "Seychelles": "SYC",
    "Sierra Leone": "SLE",
    "Somalia": "SOM",
    "South Sudan": "SSD",
    "Sudan": "SDN",
    "Tanzania": "TZA",
    "United Republic of Tanzania": "TZA",
    "Togo": "TGO",
    "Tunisia": "TUN",
    "Uganda": "UGA",
    "Zambia": "ZMB",
    "Zimbabwe": "ZWE",

    # Additional Asia
    "Afghanistan": "AFG",
    "Armenia": "ARM",
    "Azerbaijan": "AZE",
    "Bahrain": "BHR",
    "Bhutan": "BTN",
    "Brunei": "BRN",
    "Brunei Darussalam": "BRN",
    "Cambodia": "KHM",
    "Cyprus": "CYP",
    "Georgia": "GEO",
    "Iraq": "IRQ",
    "Jordan": "JOR",
    "Kazakhstan": "KAZ",
    "Kuwait": "KWT",
    "Kyrgyzstan": "KGZ",
    "Laos": "LAO",
    "Lao PDR": "LAO",
    "Lebanon": "LBN",
    "Maldives": "MDV",
    "Mongolia": "MNG",
    "Myanmar": "MMR",
    "Burma": "MMR",
    "Nepal": "NPL",
    "North Korea": "PRK",
    "Democratic People's Republic of Korea": "PRK",
    "Oman": "OMN",
    "Palestine": "PSE",
    "State of Palestine": "PSE",
    "Qatar": "QAT",
    "Sri Lanka": "LKA",
    "Syria": "SYR",
    "Syrian Arab Republic": "SYR",
    "Tajikistan": "TJK",
    "Timor-Leste": "TLS",
    "East Timor": "TLS",
    "Turkmenistan": "TKM",
    "Uzbekistan": "UZB",
    "Yemen": "YEM",
    "Hong Kong": "HKG",
    # Additional Europe
    "Austria": "AUT",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Denmark": "DNK",
    "Finland": "FIN",
    "Ireland": "IRL",
    "Norway": "NOR",
    "Switzerland": "CHE",
    # Americas
    "Argentina": "ARG",
    "Chile": "CHL",
    "Colombia": "COL",
    "Cuba": "CUB",
    "Ecuador": "ECU",
    "Nicaragua": "NIC",
    "Peru": "PER",
    "Puerto Rico": "PRI",
    # Oceania
    "Samoa": "WSM",
}

def normalize_country_code(country_input: str) -> str:
    """
    Try to normalize country input to ISO3 code.
    
    Handles various formats: ISO3 codes, ISO2 codes, country names, variants.
    
    Args:
        country_input: Country identifier (ISO3, ISO2, name, or variant).
        
    Returns:
        ISO3 country code if found, otherwise the original input.
    """
    if not country_input or not isinstance(country_input, str):
        return country_input
    
    country_input = str(country_input).strip()
    
    # Check if already ISO3
    if country_input.upper() in ISO3_TO_ISO2:
        return country_input.upper()
    
    # Check if ISO2
    if country_input.upper() in ISO2_TO_ISO3:
        return ISO2_TO_ISO3[country_input.upper()]
    
    # Check name variants
    if country_input in COUNTRY_NAME_VARIANTS:
        return COUNTRY_NAME_VARIANTS[country_input]
    
    if country_input.title() in COUNTRY_NAME_VARIANTS:
        return COUNTRY_NAME_VARIANTS[country_input.title()]
    
    # Return original if no normalization possible
    return country_input
