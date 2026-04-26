import numpy as np
import pandas as pd
from src.automation.utils.indicators import TechnicalIndicators


class AdvancedOTCPredictor:
    """Advanced prediction algorithm specifically designed for OTC markets"""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.model_type = config.get('prediction.model_type', 'advanced_otc')
        self.confidence_threshold = config.get('prediction.confidence_threshold', 0.65)
        self.lookback_period = config.get('prediction.lookback_period', 20)
        self.min_data_points = config.get('prediction.min_data_points', 30)  # Lower for faster signals
        
        # Prediction statistics
        self.total_predictions = 0
        self.correct_predictions = 0
        self.accuracy = 0.0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
        # Market regime tracking
        self.market_regime = {}  # Track if market is trending or ranging
        
    async def predict(self, symbol, timeframe, candle_history):
        """Advanced OTC prediction with multiple analysis layers"""
        if len(candle_history) < self.min_data_points:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'direction': 'NEUTRAL',
                'confidence': 0.0,
                'reason': f'Insufficient data ({len(candle_history)}/{self.min_data_points})'
            }
        
        # Extract price data
        close_prices = np.array([candle['close'] for candle in candle_history])
        high_prices = np.array([candle['high'] for candle in candle_history])
        low_prices = np.array([candle['low'] for candle in candle_history])
        volumes = np.array([candle['volume'] for candle in candle_history])
        
        # Multi-layer analysis
        layer1 = self._trend_analysis(close_prices, high_prices, low_prices)
        layer2 = self._momentum_analysis(close_prices, volumes)
        layer3 = self._pattern_recognition(close_prices, high_prices, low_prices)
        layer4 = self._volatility_analysis(close_prices, high_prices, low_prices)
        layer5 = self._market_regime_analysis(symbol, close_prices)
        
        # Weighted scoring (OTC-specific weights)
        weights = {
            'trend': 0.25,
            'momentum': 0.20,
            'pattern': 0.30,  # Higher weight for patterns in OTC
            'volatility': 0.15,
            'regime': 0.10
        }
        
        bullish_score = (
            layer1['bullish'] * weights['trend'] +
            layer2['bullish'] * weights['momentum'] +
            layer3['bullish'] * weights['pattern'] +
            layer4['bullish'] * weights['volatility'] +
            layer5['bullish'] * weights['regime']
        )
        
        bearish_score = (
            layer1['bearish'] * weights['trend'] +
            layer2['bearish'] * weights['momentum'] +
            layer3['bearish'] * weights['pattern'] +
            layer4['bearish'] * weights['volatility'] +
            layer5['bearish'] * weights['regime']
        )
        
        # Determine direction and confidence
        total_score = bullish_score + bearish_score
        if total_score == 0:
            direction = 'NEUTRAL'
            confidence = 0.5
        else:
            if bullish_score > bearish_score:
                direction = 'BUY'
                confidence = bullish_score / total_score
            elif bearish_score > bullish_score:
                direction = 'SELL'
                confidence = bearish_score / total_score
            else:
                direction = 'NEUTRAL'
                confidence = 0.5
        
        # Collect reasons
        reasons = []
        reasons.extend(layer1.get('reasons', []))
        reasons.extend(layer2.get('reasons', []))
        reasons.extend(layer3.get('reasons', []))
        reasons.extend(layer4.get('reasons', []))
        
        # Update statistics
        self.total_predictions += 1
        
        result = {
            'symbol': symbol,
            'timeframe': timeframe,
            'direction': direction,
            'confidence': confidence,
            'reasons': reasons[:5],  # Top 5 reasons
            'indicators': {
                'rsi': layer2.get('rsi', 50),
                'macd_histogram': layer2.get('macd_hist', 0),
                'sma_20': layer1.get('sma', close_prices[-1]),
                'trend_strength': layer1.get('strength', 0),
                'volatility': layer4.get('atr_pct', 0),
                'pattern': layer3.get('pattern', 'none')
            }
        }
        
        self.logger.debug(f"OTC Prediction: {direction} ({confidence:.2f}) for {symbol}")
        return result
    
    def _trend_analysis(self, close, high, low):
        """Comprehensive trend analysis"""
        bullish = 0
        bearish = 0
        reasons = []
        
        # Multiple SMAs
        sma_10 = TechnicalIndicators.calculate_sma(close, 10).iloc[-1]
        sma_20 = TechnicalIndicators.calculate_sma(close, 20).iloc[-1]
        sma_50 = TechnicalIndicators.calculate_sma(close, 50).iloc[-1] if len(close) >= 50 else sma_20
        
        current_price = close[-1]
        
        # Price vs SMAs
        if current_price > sma_10 > sma_20 > sma_50:
            bullish += 3
            reasons.append("Strong uptrend (price>SMA10>20>50)")
        elif current_price < sma_10 < sma_20 < sma_50:
            bearish += 3
            reasons.append("Strong downtrend (price<SMA10<20<50)")
        elif current_price > sma_20:
            bullish += 1
            reasons.append("Price above SMA20")
        elif current_price < sma_20:
            bearish += 1
            reasons.append("Price below SMA20")
        
        # EMA crossover
        ema_12 = TechnicalIndicators.calculate_ema(close, 12).iloc[-1]
        ema_26 = TechnicalIndicators.calculate_ema(close, 26).iloc[-1]
        
        if ema_12 > ema_26:
            bullish += 2
            reasons.append("EMA bullish crossover")
        else:
            bearish += 2
            reasons.append("EMA bearish crossover")
        
        # ADX for trend strength
        adx = self._calculate_adx(high, low, close, 14)
        trend_strength = adx / 100.0
        
        if adx > 25:
            reasons.append(f"Strong trend (ADX: {adx:.1f})")
        else:
            reasons.append(f"Weak trend (ADX: {adx:.1f})")
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'sma': sma_20,
            'strength': trend_strength
        }
    
    def _momentum_analysis(self, close, volumes):
        """Advanced momentum analysis"""
        bullish = 0
        bearish = 0
        reasons = []
        
        # RSI with OTC-specific levels
        rsi = TechnicalIndicators.calculate_rsi(close, 14).iloc[-1]
        
        if rsi < 25:
            bullish += 3
            reasons.append(f"RSI deeply oversold ({rsi:.1f})")
        elif rsi > 75:
            bearish += 3
            reasons.append(f"RSI deeply overbought ({rsi:.1f})")
        elif rsi < 40:
            bullish += 2
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 60:
            bearish += 2
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi < 50:
            bullish += 1
        else:
            bearish += 1
        
        # MACD
        macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(close)
        macd_hist = histogram.iloc[-1]
        
        if macd_hist > 0:
            bullish += 2
            reasons.append("MACD bullish momentum")
        else:
            bearish += 2
            reasons.append("MACD bearish momentum")
        
        # MACD crossover
        if len(histogram) >= 2:
            if histogram.iloc[-1] > 0 and histogram.iloc[-2] < 0:
                bullish += 3
                reasons.append("MACD bullish crossover")
            elif histogram.iloc[-1] < 0 and histogram.iloc[-2] > 0:
                bearish += 3
                reasons.append("MACD bearish crossover")
        
        # Volume analysis
        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        current_volume = volumes[-1]
        
        if current_volume > avg_volume * 1.5:
            reasons.append("High volume confirmation")
            if close[-1] > close[-2]:
                bullish += 1
            else:
                bearish += 1
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'rsi': rsi,
            'macd_hist': macd_hist
        }
    
    def _pattern_recognition(self, close, high, low):
        """Candlestick pattern recognition for OTC"""
        bullish = 0
        bearish = 0
        reasons = []
        pattern = "none"
        
        if len(close) < 5:
            return {'bullish': 0, 'bearish': 0, 'reasons': [], 'pattern': 'none'}
        
        # Get recent candles
        o1, o2, o3 = close[-3], close[-2], close[-1]
        
        # Bullish Engulfing
        if len(close) >= 2:
            if close[-2] < close[-3] and close[-1] > close[-2]:
                bullish += 4
                pattern = "Bullish Engulfing"
                reasons.append("Bullish Engulfing pattern")
        
        # Bearish Engulfing
        if len(close) >= 2:
            if close[-2] > close[-3] and close[-1] < close[-2]:
                bearish += 4
                pattern = "Bearish Engulfing"
                reasons.append("Bearish Engulfing pattern")
        
        # Hammer pattern
        if len(close) >= 2:
            body = abs(close[-1] - close[-2])
            lower_shadow = min(close[-2], close[-1]) - low[-1]
            upper_shadow = high[-1] - max(close[-2], close[-1])
            
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                bullish += 3
                pattern = "Hammer"
                reasons.append("Hammer pattern detected")
        
        # Doji (indecision)
        if len(close) >= 1:
            body = abs(close[-1] - close[-2]) if len(close) >= 2 else 0
            candle_range = high[-1] - low[-1]
            if candle_range > 0 and body / candle_range < 0.1:
                reasons.append("Doji pattern (indecision)")
        
        # Three white soldiers / black crows
        if len(close) >= 3:
            if close[-1] > close[-2] > close[-3]:
                bullish += 2
                pattern = "Three White Soldiers"
                reasons.append("Three consecutive bullish candles")
            elif close[-1] < close[-2] < close[-3]:
                bearish += 2
                pattern = "Three Black Crows"
                reasons.append("Three consecutive bearish candles")
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'pattern': pattern
        }
    
    def _volatility_analysis(self, close, high, low):
        """Volatility-based analysis for OTC"""
        bullish = 0
        bearish = 0
        reasons = []
        
        # ATR (Average True Range)
        atr = TechnicalIndicators.calculate_atr(high, low, close, 14).iloc[-1]
        atr_pct = (atr / close[-1]) * 100
        
        # Bollinger Bands
        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(close, 20, 2)
        
        if close[-1] <= lower.iloc[-1]:
            bullish += 3
            reasons.append("Price at lower Bollinger Band")
        elif close[-1] >= upper.iloc[-1]:
            bearish += 3
            reasons.append("Price at upper Bollinger Band")
        elif close[-1] < middle.iloc[-1]:
            bearish += 1
        else:
            bullish += 1
        
        # Volatility contraction/expansion
        if len(close) >= 20:
            recent_vol = np.std(close[-5:])
            avg_vol = np.std(close[-20:])
            
            if recent_vol < avg_vol * 0.5:
                reasons.append("Low volatility (breakout imminent)")
            elif recent_vol > avg_vol * 1.5:
                reasons.append("High volatility")
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'atr_pct': atr_pct
        }
    
    def _market_regime_analysis(self, symbol, close):
        """Detect market regime (trending vs ranging)"""
        bullish = 0
        bearish = 0
        
        if len(close) < 50:
            return {'bullish': 0, 'bearish': 0}
        
        # Calculate trend consistency
        recent_trend = close[-10:]
        up_moves = sum(1 for i in range(1, len(recent_trend)) if recent_trend[i] > recent_trend[i-1])
        
        if up_moves >= 7:
            bullish += 2
        elif up_moves <= 3:
            bearish += 2
        
        return {'bullish': bullish, 'bearish': bearish}
    
    def _calculate_adx(self, high, low, close, period=14):
        """Calculate ADX (Average Directional Index)"""
        if len(close) < period + 1:
            return 25
        
        # +DM and -DM
        high_diff = np.diff(high)
        low_diff = np.diff(low)
        
        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
        
        # TR (True Range)
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        
        # Smoothed averages
        atr = np.mean(tr[-period:])
        plus_di = (np.mean(plus_dm[-period:]) / atr) * 100 if atr > 0 else 0
        minus_di = (np.mean(minus_dm[-period:]) / atr) * 100 if atr > 0 else 0
        
        # DX and ADX
        if plus_di + minus_di == 0:
            return 25
        
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        return min(dx, 100)
    
    def update_accuracy(self, predicted, actual):
        """Update prediction accuracy"""
        if predicted == actual:
            self.correct_predictions += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        if self.total_predictions > 0:
            self.accuracy = self.correct_predictions / self.total_predictions
    
    def get_stats(self):
        """Get detailed statistics"""
        return {
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy': self.accuracy,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses
        }
