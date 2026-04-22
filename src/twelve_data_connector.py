import logging
import os
import time
from typing import Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class TwelveDataConnector:
    BASE_URL = "https://api.twelvedata.com/time_series"

    SYMBOL_MAP = {
        "EUR/USD": "EUR/USD",
        "GBP/USD": "GBP/USD",
        "USD/JPY": "USD/JPY",
        "AUD/USD": "AUD/USD",
        "USD/CAD": "USD/CAD",
        "NZD/USD": "NZD/USD",
        "USD/CHF": "USD/CHF",
        "EUR/GBP": "EUR/GBP",
        "AUD/JPY": "AUD/JPY",
        "CAD/CHF": "CAD/CHF",
        "GBP/CAD": "GBP/CAD",
        "CHF/JPY": "CHF/JPY",
        "EUR/CHF": "EUR/CHF",
        "GBP/AUD": "GBP/AUD",
        "GBP/CHF": "GBP/CHF",
        "USD/INR": "USD/INR",
        "XAU/USD": "XAU/USD",
        "XAG/USD": "XAG/USD",
        "EUR/USD-OTC": "EUR/USD",
        "GBP/USD-OTC": "GBP/USD",
        "USD/JPY-OTC": "USD/JPY",
        "AUD/USD-OTC": "AUD/USD",
        "USD/CAD-OTC": "USD/CAD",
        "NZD/USD-OTC": "NZD/USD",
        "USD/CHF-OTC": "USD/CHF",
        "EUR/GBP-OTC": "EUR/GBP",
        "AUD/JPY-OTC": "AUD/JPY",
        "CAD/CHF-OTC": "CAD/CHF",
        "GBP/CAD-OTC": "GBP/CAD",
        "CHF/JPY-OTC": "CHF/JPY",
        "EUR/CHF-OTC": "EUR/CHF",
        "GBP/AUD-OTC": "GBP/AUD",
        "GBP/CHF-OTC": "GBP/CHF",
        "USD/INR-OTC": "USD/INR",
        "XAU/USD-OTC": "XAU/USD",
        "XAG/USD-OTC": "XAG/USD",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY", "").strip()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (QuotexOTCBot/1.0)"})
        self.last_fetch_time = time.time()

    def _symbol_to_twelve_data(self, symbol: str) -> str:
        return self.SYMBOL_MAP.get(symbol.upper(), symbol.replace("-OTC", ""))

    def _interval_to_twelve_data(self, interval: str) -> str:
        if interval.endswith("s"):
            seconds = int(interval[:-1])
        elif interval.isdigit():
            seconds = int(interval)
        else:
            return "1min"

        if seconds < 180:
            return "1min"
        if seconds < 900:
            return "5min"
        if seconds < 1800:
            return "15min"
        if seconds < 3600:
            return "30min"
        return "1h"

    def start_websocket(self, symbols):
        return None

    def stop_websocket(self):
        return None

    def get_latency(self) -> float:
        return round((time.time() - self.last_fetch_time) * 1000, 2)

    def _fetch_time_series(self, symbol: str, interval: str, output_size: int) -> Optional[pd.DataFrame]:
        if not self.api_key:
            logger.error("TWELVE_DATA_API_KEY is missing")
            return None

        try:
            response = self.session.get(
                self.BASE_URL,
                params={
                    "symbol": self._symbol_to_twelve_data(symbol),
                    "interval": interval,
                    "outputsize": min(max(output_size, 50), 5000),
                    "apikey": self.api_key,
                    "format": "JSON",
                    "order": "asc",
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "ok":
                logger.error("Twelve Data error for %s: %s", symbol, payload.get("message", payload))
                return None

            values = payload.get("values", [])
            if not values:
                return None

            df = pd.DataFrame(values)
            df["datetime"] = pd.to_datetime(df["datetime"])
            for column in ["open", "high", "low", "close", "volume"]:
                if column in df.columns:
                    df[column] = pd.to_numeric(df[column], errors="coerce")
                else:
                    df[column] = 1.0 if column == "volume" else None

            df["volume"] = df["volume"].fillna(1.0)
            df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
            self.last_fetch_time = time.time()
            return df
        except Exception as exc:
            logger.error("Twelve Data fetch error for %s: %s", symbol, exc)
            return None

    def get_time_series(self, symbol: str, interval: str = "1m", output_size: int = 300) -> Optional[pd.DataFrame]:
        return self._fetch_time_series(symbol, self._interval_to_twelve_data(interval), output_size)

    def get_mtf_trend(self, symbol: str) -> str:
        df = self._fetch_time_series(symbol, "5min", 80)
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
            logger.error("Twelve Data indicator calculation error: %s", exc)
            return {}
