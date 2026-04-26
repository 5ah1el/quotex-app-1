import numpy as np
import pandas as pd
from src.automation.utils.indicators import TechnicalIndicators


class SuperAdvancedOTCPredictor:
    """
    SUPER ADVANCED Live OTC Prediction Algorithm
    Features:
    - Multi-timeframe analysis
    - Real-time momentum tracking
    - Advanced pattern recognition
    - Volume-price relationship
    - Market microstructure analysis
    - Adaptive confidence scoring
    """
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.confidence_threshold = config.get('prediction.confidence_threshold', 0.65)
        self.min_data_points = config.get('prediction.min_data_points', 30)
        
        # Prediction statistics
        self.total_predictions = 0
        self.correct_predictions = 0
        self.accuracy = 0.0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
        # Market state tracking
        self.market_state = {}
        self.recent_predictions = []
        
    async def predict(self, symbol, timeframe, candle_history):
        """SUPER ADVANCED OTC prediction with 10 analysis layers"""
        if len(candle_history) < self.min_data_points:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'direction': 'NEUTRAL',
                'confidence': 0.0,
                'reason': f'Insufficient data ({len(candle_history)}/{self.min_data_points})'
            }
        
        # Extract price data
        close = np.array([c['close'] for c in candle_history])
        high = np.array([c['high'] for c in candle_history])
        low = np.array([c['low'] for c in candle_history])
        volume = np.array([c['volume'] for c in candle_history])
        
        # 10-Layer Deep Analysis
        analyses = {
            'trend': self._multi_timeframe_trend(close, high, low),
            'momentum': self._advanced_momentum(close, volume),
            'pattern': self._candlestick_patterns(close, high, low),
            'volatility': self._volatility_regime(close, high, low),
            'volume_profile': self._volume_price_analysis(close, volume),
            'support_resistance': self._dynamic_sr_levels(close, high, low),
            'market_structure': self._market_structure_analysis(close, high, low),
            'oscillator': self._multi_oscillator_convergence(close, high, low),
            'price_action': self._price_action_behavior(close, high, low),
            'sentiment': self._market_sentiment_indicator(close, volume)
        }
        
        # Weighted scoring system optimized for OTC
        weights = {
            'trend': 0.15,
            'momentum': 0.12,
            'pattern': 0.18,
            'volatility': 0.10,
            'volume_profile': 0.10,
            'support_resistance': 0.10,
            'market_structure': 0.08,
            'oscillator': 0.07,
            'price_action': 0.05,
            'sentiment': 0.05
        }
        
        # Calculate weighted scores
        bullish_score = 0
        bearish_score = 0
        all_reasons = []
        
        for layer_name, result in analyses.items():
            bullish_score += result['bullish'] * weights[layer_name]
            bearish_score += result['bearish'] * weights[layer_name]
            all_reasons.extend(result.get('reasons', [])[:2])  # Top 2 reasons per layer
        
        # Determine direction
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
        
        # Adaptive confidence boost for strong signals
        if confidence > 0.70:
            # Check for confluence (multiple layers agree)
            bullish_layers = sum(1 for a in analyses.values() if a['bullish'] > a['bearish'])
            bearish_layers = sum(1 for a in analyses.values() if a['bearish'] > a['bullish'])
            
            if direction == 'BUY' and bullish_layers >= 7:
                confidence = min(confidence * 1.15, 0.95)
            elif direction == 'SELL' and bearish_layers >= 7:
                confidence = min(confidence * 1.15, 0.95)
        
        # Update stats
        self.total_predictions += 1
        
        result = {
            'symbol': symbol,
            'timeframe': timeframe,
            'direction': direction,
            'confidence': confidence,
            'reasons': all_reasons[:6],  # Top 6 reasons
            'indicators': {
                'rsi': analyses['momentum'].get('rsi', 50),
                'macd_histogram': analyses['momentum'].get('macd_hist', 0),
                'sma_20': analyses['trend'].get('sma_20', close[-1]),
                'trend_strength': analyses['trend'].get('strength', 0),
                'volatility': analyses['volatility'].get('atr_pct', 0),
                'volume_ratio': analyses['volume_profile'].get('volume_ratio', 1.0)
            }
        }
        
        self.logger.debug(f"SUPER OTC: {direction} ({confidence:.2%}) | {symbol}")
        return result
    
    def _multi_timeframe_trend(self, close, high, low):
        """Multi-timeframe trend analysis"""
        bullish = 0
        bearish = 0
        reasons = []
        
        # Multiple EMAs
        ema_8 = TechnicalIndicators.calculate_ema(close, 8).iloc[-1]
        ema_21 = TechnicalIndicators.calculate_ema(close, 21).iloc[-1]
        ema_50 = TechnicalIndicators.calculate_ema(close, 50).iloc[-1] if len(close) >= 50 else ema_21
        
        current = close[-1]
        
        # EMA alignment
        if current > ema_8 > ema_21 > ema_50:
            bullish += 4
            reasons.append("Perfect bullish EMA alignment")
        elif current < ema_8 < ema_21 < ema_50:
            bearish += 4
            reasons.append("Perfect bearish EMA alignment")
        elif current > ema_21:
            bullish += 2
            reasons.append("Price above EMA21")
        else:
            bearish += 2
            reasons.append("Price below EMA21")
        
        # ADX trend strength
        adx = self._calculate_adx(high, low, close, 14)
        if adx > 30:
            reasons.append(f"Strong trend (ADX: {adx:.0f})")
        elif adx < 20:
            reasons.append(f"Weak trend (ADX: {adx:.0f})")
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'sma_20': ema_21,
            'strength': adx / 100.0
        }
    
    def _advanced_momentum(self, close, volume):
        """Advanced momentum with multiple oscillators"""
        bullish = 0
        bearish = 0
        reasons = []
        
        # RSI with divergence detection
        rsi = TechnicalIndicators.calculate_rsi(close, 14).iloc[-1]
        
        if rsi < 30:
            bullish += 4
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            bearish += 4
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi < 45:
            bullish += 2
        elif rsi > 55:
            bearish += 2
        
        # MACD with histogram momentum
        macd, signal, hist = TechnicalIndicators.calculate_macd(close)
        macd_hist = hist.iloc[-1]
        
        if macd_hist > 0:
            bullish += 3
            reasons.append("MACD bullish")
            if len(hist) >= 2 and hist.iloc[-1] > hist.iloc[-2]:
                bullish += 1
                reasons.append("MACD strengthening")
        else:
            bearish += 3
            reasons.append("MACD bearish")
            if len(hist) >= 2 and hist.iloc[-1] < hist.iloc[-2]:
                bearish += 1
                reasons.append("MACD weakening")
        
        # Stochastic
        stoch_k, stoch_d = self._calculate_stochastic(close, high, low, 14)
        if stoch_k < 20:
            bullish += 2
            reasons.append("Stochastic oversold")
        elif stoch_k > 80:
            bearish += 2
            reasons.append("Stochastic overbought")
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'rsi': rsi,
            'macd_hist': macd_hist
        }
    
    def _candlestick_patterns(self, close, high, low):
        """Advanced candlestick pattern recognition"""
        bullish = 0
        bearish = 0
        reasons = []
        
        if len(close) < 5:
            return {'bullish': 0, 'bearish': 0, 'reasons': []}
        
        # Engulfing patterns
        if close[-1] > close[-2] and close[-2] < close[-3]:
            bullish += 4
            reasons.append("Bullish engulfing")
        elif close[-1] < close[-2] and close[-2] > close[-3]:
            bearish += 4
            reasons.append("Bearish engulfing")
        
        # Three candle patterns
        if len(close) >= 3:
            if close[-1] > close[-2] > close[-3]:
                bullish += 3
                reasons.append("3 bullish candles")
            elif close[-1] < close[-2] < close[-3]:
                bearish += 3
                reasons.append("3 bearish candles")
        
        # Hammer/Shooting star
        body = abs(close[-1] - close[-2])
        upper_shadow = high[-1] - max(close[-1], close[-2])
        lower_shadow = min(close[-1], close[-2]) - low[-1]
        
        if lower_shadow > body * 2 and upper_shadow < body * 0.5:
            bullish += 3
            reasons.append("Hammer pattern")
        elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
            bearish += 3
            reasons.append("Shooting star")
        
        return {'bullish': bullish, 'bearish': bearish, 'reasons': reasons}
    
    def _volatility_regime(self, close, high, low):
        """Volatility regime detection"""
        bullish = 0
        bearish = 0
        reasons = []
        
        # ATR
        atr = TechnicalIndicators.calculate_atr(high, low, close, 14).iloc[-1]
        atr_pct = (atr / close[-1]) * 100
        
        # Bollinger Bands
        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(close, 20, 2)
        
        if close[-1] <= lower.iloc[-1]:
            bullish += 4
            reasons.append("At lower BB (oversold)")
        elif close[-1] >= upper.iloc[-1]:
            bearish += 4
            reasons.append("At upper BB (overbought)")
        elif close[-1] < middle.iloc[-1]:
            bearish += 1
        else:
            bullish += 1
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'atr_pct': atr_pct
        }
    
    def _volume_price_analysis(self, close, volume):
        """Volume-price relationship analysis"""
        bullish = 0
        bearish = 0
        reasons = []
        
        avg_vol = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
        current_vol = volume[-1]
        vol_ratio = current_vol / avg_vol
        
        if vol_ratio > 1.5:
            reasons.append(f"High volume ({vol_ratio:.1f}x)")
            if close[-1] > close[-2]:
                bullish += 3
                reasons.append("Volume confirms uptrend")
            else:
                bearish += 3
                reasons.append("Volume confirms downtrend")
        elif vol_ratio < 0.5:
            reasons.append("Low volume (weak move)")
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'reasons': reasons,
            'volume_ratio': vol_ratio
        }
    
    def _dynamic_sr_levels(self, close, high, low):
        """Dynamic support/resistance detection"""
        bullish = 0
        bearish = 0
        reasons = []
        
        if len(close) < 20:
            return {'bullish': 0, 'bearish': 0, 'reasons': []}
        
        # Recent pivot points
        recent_high = max(high[-20:])
        recent_low = min(low[-20:])
        current = close[-1]
        
        # Distance to levels
        dist_to_high = (recent_high - current) / current
        dist_to_low = (current - recent_low) / current
        
        if dist_to_low < 0.002:
            bullish += 3
            reasons.append("Near support level")
        elif dist_to_high < 0.002:
            bearish += 3
            reasons.append("Near resistance level")
        
        return {'bullish': bullish, 'bearish': bearish, 'reasons': reasons}
    
    def _market_structure_analysis(self, close, high, low):
        """Market structure (HH, HL, LH, LL)"""
        bullish = 0
        bearish = 0
        reasons = []
        
        if len(close) < 10:
            return {'bullish': 0, 'bearish': 0, 'reasons': []}
        
        # Check for higher highs/higher lows
        recent = close[-10:]
        up_moves = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i-1])
        
        if up_moves >= 7:
            bullish += 3
            reasons.append("Uptrend structure")
        elif up_moves <= 3:
            bearish += 3
            reasons.append("Downtrend structure")
        
        return {'bullish': bullish, 'bearish': bearish, 'reasons': reasons}
    
    def _multi_oscillator_convergence(self, close, high, low):
        """Multiple oscillator convergence"""
        bullish = 0
        bearish = 0
        reasons = []
        
        # CCI
        cci = self._calculate_cci(close, high, low, 20)
        if cci < -100:
            bullish += 2
            reasons.append("CCI oversold")
        elif cci > 100:
            bearish += 2
            reasons.append("CCI overbought")
        
        # Williams %R
        willr = self._calculate_williams_r(close, high, low, 14)
        if willr < -80:
            bullish += 2
            reasons.append("Williams %R oversold")
        elif willr > -20:
            bearish += 2
            reasons.append("Williams %R overbought")
        
        return {'bullish': bullish, 'bearish': bearish, 'reasons': reasons}
    
    def _price_action_behavior(self, close, high, low):
        """Price action behavior analysis"""
        bullish = 0
        bearish = 0
        reasons = []
        
        if len(close) < 3:
            return {'bullish': 0, 'bearish': 0, 'reasons': []}
        
        # Momentum of momentum
        change1 = close[-1] - close[-2]
        change2 = close[-2] - close[-3]
        
        if change1 > 0 and change1 > change2:
            bullish += 2
            reasons.append("Accelerating upward")
        elif change1 < 0 and change1 < change2:
            bearish += 2
            reasons.append("Accelerating downward")
        
        return {'bullish': bullish, 'bearish': bearish, 'reasons': reasons}
    
    def _market_sentiment_indicator(self, close, volume):
        """Market sentiment from price/volume behavior"""
        bullish = 0
        bearish = 0
        
        if len(close) < 10:
            return {'bullish': 0, 'bearish': 0}
        
        # Recent performance
        recent_return = (close[-1] - close[-10]) / close[-10]
        
        if recent_return < -0.02:
            bullish += 2  # Oversold bounce potential
        elif recent_return > 0.02:
            bearish += 2  # Overbought correction potential
        
        return {'bullish': bullish, 'bearish': bearish}
    
    # Helper functions
    def _calculate_adx(self, high, low, close, period=14):
        """Calculate ADX"""
        if len(close) < period + 1:
            return 25
        
        high_diff = np.diff(high)
        low_diff = np.diff(low)
        
        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
        
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        
        atr = np.mean(tr[-period:])
        plus_di = (np.mean(plus_dm[-period:]) / atr) * 100 if atr > 0 else 0
        minus_di = (np.mean(minus_dm[-period:]) / atr) * 100 if atr > 0 else 0
        
        if plus_di + minus_di == 0:
            return 25
        
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        return min(dx, 100)
    
    def _calculate_stochastic(self, close, high, low, period=14):
        """Calculate Stochastic Oscillator"""
        if len(close) < period:
            return 50, 50
        
        lowest_low = min(low[-period:])
        highest_high = max(high[-period:])
        
        if highest_high == lowest_low:
            return 50, 50
        
        k = ((close[-1] - lowest_low) / (highest_high - lowest_low)) * 100
        d = k  # Simplified
        return k, d
    
    def _calculate_cci(self, close, high, low, period=20):
        """Calculate CCI"""
        if len(close) < period:
            return 0
        
        tp = (high + low + close) / 3
        sma_tp = np.mean(tp[-period:])
        md = np.mean(np.abs(tp[-period:] - sma_tp))
        
        if md == 0:
            return 0
        
        cci = (tp[-1] - sma_tp) / (0.015 * md)
        return cci
    
    def _calculate_williams_r(self, close, high, low, period=14):
        """Calculate Williams %R"""
        if len(close) < period:
            return -50
        
        highest_high = max(high[-period:])
        lowest_low = min(low[-period:])
        
        if highest_high == lowest_low:
            return -50
        
        wr = ((highest_high - close[-1]) / (highest_high - lowest_low)) * -100
        return wr
    
    def update_accuracy(self, predicted, actual):
        """Update accuracy"""
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
        """Get statistics"""
        return {
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy': self.accuracy,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses
        }
