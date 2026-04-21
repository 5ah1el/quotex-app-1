import logging
import time
from typing import Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class YahooConnector:
    CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    SYMBOL_MAP = {
        "EUR/USD-OTC": "EURUSD=X",
        "GBP/USD-OTC": "GBPUSD=X",
        "USD/JPY-OTC": "JPY=X",
        "AUD/USD-OTC": "AUDUSD=X",
        "USD/CAD-OTC": "CAD=X",
        "NZD/USD-OTC": "NZDUSD=X",
        "USD/CHF-OTC": "CHF=X",
        "EUR/GBP-OTC": "EURGBP=X",
        "AUD/JPY-OTC": "AUDJPY=X",
        "CAD/CHF-OTC": "CADCHF=X",
        "GBP/CAD-OTC": "GBPCAD=X",
        "CHF/JPY-OTC": "CHFJPY=X",
        "EUR/CHF-OTC": "EURCHF=X",
        "GBP/AUD-OTC": "GBPAUD=X",
        "GBP/CHF-OTC": "GBPCHF=X",
        "USD/INR-OTC": "INR=X",
        "XAU/USD-OTC": "GC=F",
        "XAG/USD-OTC": "SI=F",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (YahooOTCSignalBot/1.0)"})
        self.last_fetch_time = time.time()

    def _symbol_to_yahoo(self, symbol: str) -> str:
        return self.SYMBOL_MAP.get(symbol.upper(), symbol.replace("-OTC", "").replace("/", "") + "=X")

    def _interval_to_yahoo(self, interval: str) -> str:
        if interval.endswith("s"):
            seconds = int(interval[:-1])
        elif interval.isdigit():
            seconds = int(interval)
        else:
            return "1m"

        if seconds < 180:
            return "1m"
        if seconds < 900:
            return "5m"
        if seconds < 1800:
            return "15m"
        return "30m"

    def _range_for_interval(self, interval: str) -> str:
        if interval in {"1m", "2m", "5m"}:
            return "7d"
        return "1mo"

    def start_websocket(self, symbols):
        return None

    def stop_websocket(self):
        return None

    def get_latency(self) -> float:
        return round((time.time() - self.last_fetch_time) * 1000, 2)

    def get_time_series(self, symbol: str, interval: str = "1m", output_size: int = 300) -> Optional[pd.DataFrame]:
        yahoo_symbol = self._symbol_to_yahoo(symbol)
        yahoo_interval = self._interval_to_yahoo(interval)

        try:
            response = self.session.get(
                self.CHART_URL.format(symbol=yahoo_symbol),
                params={
                    "interval": yahoo_interval,
                    "range": self._range_for_interval(yahoo_interval),
                    "includePrePost": "false",
                    "events": "div,splits",
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("chart", {}).get("result", [])
            if not result:
                return None

            result = result[0]
            timestamps = result.get("timestamp", [])
            quotes = result.get("indicators", {}).get("quote", [])
            if not timestamps or not quotes:
                return None

            quote = quotes[0]
            df = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(timestamps, unit="s"),
                    "open": pd.to_numeric(quote.get("open", []), errors="coerce"),
                    "high": pd.to_numeric(quote.get("high", []), errors="coerce"),
                    "low": pd.to_numeric(quote.get("low", []), errors="coerce"),
                    "close": pd.to_numeric(quote.get("close", []), errors="coerce"),
                    "volume": pd.to_numeric(quote.get("volume", []), errors="coerce"),
                }
            )
            df["volume"] = df["volume"].fillna(1.0)
            df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
            self.last_fetch_time = time.time()
            return df.tail(min(max(output_size, 50), len(df))).reset_index(drop=True)
        except Exception as exc:
            logger.error("Yahoo fetch error for %s: %s", symbol, exc)
            return None

    def get_mtf_trend(self, symbol: str) -> str:
        df = self.get_time_series(symbol, interval="300", output_size=80)
        if df is None or len(df) < 20:
            return "NEUTRAL"

        sma_20 = df["close"].rolling(window=20).mean().iloc[-1]
        last_close = df["close"].iloc[-1]
        if pd.isna(sma_20):
            return "NEUTRAL"
        if last_close > sma_20:
            return "BULLISH"
        if last_close < sma_20:
            return "BEARISH"
        return "NEUTRAL"

    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 50:
            return {}

        try:
            close = df["close"]
            sma_20 = close.rolling(window=20).mean()
            sma_50 = close.rolling(window=50).mean()

            delta = close.diff()
            gain = delta.clip(lower=0).rolling(window=14).mean()
            loss = (-delta.clip(upper=0)).rolling(window=14).mean()
            rs = gain / loss.replace(0, 1e-9)
            rsi = 100 - (100 / (1 + rs))

            ema_12 = close.ewm(span=12, adjust=False).mean()
            ema_26 = close.ewm(span=26, adjust=False).mean()
            macd = ema_12 - ema_26
            macd_signal = macd.ewm(span=9, adjust=False).mean()

            std = close.rolling(window=20).std()
            upper_band = sma_20 + (std * 2)
            lower_band = sma_20 - (std * 2)

            return {
                "sma_20": float(sma_20.iloc[-1]),
                "sma_50": float(sma_50.iloc[-1]),
                "rsi": float(rsi.iloc[-1]),
                "current_price": float(close.iloc[-1]),
                "previous_close": float(close.iloc[-2]),
                "macd": float(macd.iloc[-1]),
                "macd_signal": float(macd_signal.iloc[-1]),
                "bb_upper": float(upper_band.iloc[-1]),
                "bb_lower": float(lower_band.iloc[-1]),
                "bb_middle": float(sma_20.iloc[-1]),
            }
        except Exception as exc:
            logger.error("Yahoo indicator calculation error: %s", exc)
            return {}
