"""Static configuration: constants and reference catalogs."""

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

TRADING_DAYS = 252  # trading days per year, used to annualize returns/volatility

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "CHF": "CHF", "CAD": "C$",
    "JPY": "¥", "HKD": "HK$", "CNY": "¥",
}

# Default annual risk-free rates by currency (editable in the app sidebar).
DEFAULT_RF_RATES = {
    "USD": 0.035,
    "EUR": 0.030,
    "GBP": 0.045,
    "CHF": 0.015,
    "JPY": 0.005,
    "CAD": 0.035,
    "HKD": 0.038,
    "CNY": 0.020,
}
DEFAULT_RF_FALLBACK = 0.035

COMMODITIES_CATALOG = {
    "GC=F": "Gold Futures (COMEX)",
    "SI=F": "Silver Futures (COMEX)",
    "CL=F": "Crude Oil WTI (NYMEX)",
    "BZ=F": "Brent Crude Oil (ICE)",
    "NG=F": "Natural Gas (NYMEX)",
    "HG=F": "Copper Futures (COMEX)",
    "ZW=F": "Wheat Futures (CBOT)",
    "ZC=F": "Corn Futures (CBOT)",
    "ZS=F": "Soybean Futures (CBOT)",
}

ASIAN_FLAGSHIPS = {
    "7203.T": "Toyota Motor Corp",
    "6758.T": "Sony Group Corp",
    "9984.T": "SoftBank Group Corp",
    "8306.T": "Mitsubishi UFJ Financial",
    "8035.T": "Tokyo Electron Ltd",
    "9983.T": "Fast Retailing (Uniqlo)",
    "6861.T": "Keyence Corp",
    "7974.T": "Nintendo Co Ltd",
    "0700.HK": "Tencent Holdings",
    "9988.HK": "Alibaba Group (HK)",
    "3690.HK": "Meituan",
    "1299.HK": "AIA Group",
    "0939.HK": "China Construction Bank",
    "600519.SS": "Kweichow Moutai",
    "300750.SZ": "CATL (Contemporary Amperex)",
}