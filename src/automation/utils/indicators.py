import pandas as pd


class TechnicalIndicators:
    @staticmethod
    def _to_series(values):
        if isinstance(values, pd.Series):
            return values.astype(float)
        return pd.Series(values, dtype="float64")

    @classmethod
    def calculate_sma(cls, values, period):
        series = cls._to_series(values)
        return series.rolling(window=period, min_periods=1).mean()

    @classmethod
    def calculate_ema(cls, values, period):
        series = cls._to_series(values)
        return series.ewm(span=period, adjust=False).mean()

    @classmethod
    def calculate_rsi(cls, values, period=14):
        series = cls._to_series(values)
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(window=period, min_periods=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period, min_periods=period).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)

    @classmethod
    def calculate_macd(cls, values, fast=12, slow=26, signal=9):
        series = cls._to_series(values)
        ema_fast = cls.calculate_ema(series, fast)
        ema_slow = cls.calculate_ema(series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @classmethod
    def calculate_atr(cls, high, low, close, period=14):
        high_series = cls._to_series(high)
        low_series = cls._to_series(low)
        close_series = cls._to_series(close)
        prev_close = close_series.shift(1)
        tr = pd.concat(
            [
                high_series - low_series,
                (high_series - prev_close).abs(),
                (low_series - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    @classmethod
    def calculate_bollinger_bands(cls, values, period=20, std_dev=2):
        series = cls._to_series(values)
        middle = series.rolling(window=period, min_periods=1).mean()
        std = series.rolling(window=period, min_periods=1).std().fillna(0.0)
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower
