import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SignalEngine:
    def __init__(self):
        self.signal_history: List[Dict] = []
        self.consecutive_losses = 0
        self.recovery_mode = False

    def calculate_trend_score(self, indicators: dict) -> float:
        score = 0.0
        weight = 0.0

        price = indicators.get('current_price', 0)
        sma_20 = indicators.get('sma_20', 0)
        sma_50 = indicators.get('sma_50', 0)
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)

        if price > sma_20: score += 1.0
        elif price < sma_20: score -= 1.0
        weight += 1.0

        if sma_20 > sma_50: score += 1.5
        elif sma_20 < sma_50: score -= 1.5
        weight += 1.5

        if rsi < 30: score += 2.0
        elif rsi > 70: score -= 2.0
        weight += 2.0

        if macd > macd_signal: score += 1.5
        elif macd < macd_signal: score -= 1.5
        weight += 1.5

        trend_score = (score / weight) * 100
        return max(-100, min(100, trend_score))

    def calculate_smc_patterns(self, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 20:
            return {}

        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_p = df['open'].values

        # Market Structure
        prev_high = np.max(high[-15:-2])
        prev_low = np.min(low[-15:-2])

        structure = "NEUTRAL"
        if close[-1] > prev_high: structure = "BOS_UP"
        elif close[-1] < prev_low: structure = "BOS_DOWN"

        # FVG (Fair Value Gap)
        fvg = None
        if len(high) >= 3:
            if low[-1] > high[-3]: fvg = "BULLISH_FVG"
            elif high[-1] < low[-3]: fvg = "BEARISH_FVG"

        return {
            "structure": structure,
            "fvg": fvg,
            "regime": "TRENDING" if structure != "NEUTRAL" else "RANGING"
        }

    def detect_institutional_logic(self, df: pd.DataFrame) -> List[str]:
        """2026 Logic: Detect Liquidity Grabs, Order Flow Imbalances, and Velocity"""
        if df is None or len(df) < 15: return []
        
        logic = []
        c = df['close'].values
        h = df['high'].values
        l = df['low'].values
        o = df['open'].values
        v = df['volume'].values if 'volume' in df.columns else np.ones(len(c))

        # 1. Liquidity Grab (Institutional Sweep)
        # Look for a sweep of the 10-period high/low followed by a reversal
        sweep_high = np.max(h[-11:-1])
        sweep_low = np.min(l[-11:-1])
        
        if h[-1] > sweep_high and c[-1] < sweep_high:
            logic.append("LIQUIDITY_GRAB_HIGH")
        if l[-1] < sweep_low and c[-1] > sweep_low:
            logic.append("LIQUIDITY_GRAB_LOW")

        # 2. Order Flow Imbalance (Volume-Price Divergence)
        # High volume on a small candle = Absorption/Imbalance
        avg_vol = np.mean(v[-10:-1])
        candle_size = np.abs(c[-1] - o[-1])
        avg_candle_size = np.mean(np.abs(c[-10:-1] - o[-10:-1]))
        
        if v[-1] > avg_vol * 1.5 and candle_size < avg_candle_size * 0.5:
            if c[-1] > o[-1]: logic.append("BULLISH_ABSORPTION")
            else: logic.append("BEARISH_ABSORPTION")

        # 3. Price Velocity & Exhaustion
        # Acceleration of price movement
        velocity = (c[-1] - c[-2]) - (c[-2] - c[-3])
        if velocity > 0 and c[-1] > c[-2]: logic.append("VELOCITY_UP")
        elif velocity < 0 and c[-1] < c[-2]: logic.append("VELOCITY_DOWN")

        return logic

    def track_outcomes(self, current_price: float):
        """Analyze previous signals to detect losses and enter recovery mode."""
        if len(self.signal_history) < 2: return

        # Check the last signal that has a 'resolved' price (one candle later)
        last_sig = self.signal_history[-2]
        if 'resolved' in last_sig: return 

        direction = last_sig['direction']
        entry_price = last_sig['price']
        
        # In Binary Options, even a 1-pip difference counts
        win = False
        if direction == 'UP' and current_price > entry_price: win = True
        elif direction == 'DOWN' and current_price < entry_price: win = True
        
        last_sig['resolved'] = True
        last_sig['result'] = 'WIN' if win else 'LOSS'

        if not win:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 2:
                self.recovery_mode = True
                logger.warning(f"⚠️ {self.consecutive_losses} Consecutive Losses. RECOVERY MODE: ACTIVATED.")
        else:
            self.consecutive_losses = 0
            self.recovery_mode = False

    def detect_candle_patterns(self, df: pd.DataFrame) -> List[str]:
        """Detect high-probability candle patterns on live crypto candles."""
        if df is None or len(df) < 5: return []
        
        patterns = []
        o = df['open'].values
        h = df['high'].values
        l = df['low'].values
        c = df['close'].values
        
        # Candle sizes
        body = np.abs(c - o)
        upper_shadow = h - np.maximum(o, c)
        lower_shadow = np.minimum(o, c) - l
        full_range = h - l
        
        # 1. Hammer / Shooting Star (Pin Bars)
        if lower_shadow[-1] > body[-1] * 2 and upper_shadow[-1] < body[-1] * 0.5:
            patterns.append("BULLISH_HAMMER")
        if upper_shadow[-1] > body[-1] * 2 and lower_shadow[-1] < body[-1] * 0.5:
            patterns.append("BEARISH_STAR")
            
        # 2. Doji / Spinning Top (Indecision)
        if body[-1] < full_range[-1] * 0.1:
            patterns.append("DOJI")
        elif body[-1] < full_range[-1] * 0.3:
            patterns.append("SPINNING_TOP")
            
        # 3. Engulfing
        if c[-1] > o[-1] and o[-1] < c[-2] and c[-1] > o[-2] and c[-2] < o[-2]:
            patterns.append("BULLISH_ENGULFING")
        if c[-1] < o[-1] and o[-1] > c[-2] and c[-1] < o[-2] and c[-2] > o[-2]:
            patterns.append("BEARISH_ENGULFING")
            
        # 4. Consecutive color flip
        if all(c[i] > o[i] for i in range(-4, -1)) and c[-1] < o[-1]:
            patterns.append("COLOR_FLIP_REVERSAL_DOWN")
        if all(c[i] < o[i] for i in range(-4, -1)) and c[-1] > o[-1]:
            patterns.append("COLOR_FLIP_REVERSAL_UP")

        return patterns

    def calculate_institutional_zones(self, df: pd.DataFrame) -> Dict:
        """2026 Standard: Detect Volume-Weighted Order Blocks and Fibonacci Levels"""
        if df is None or len(df) < 30: return {}
        
        o = df['open'].values
        h = df['high'].values
        l = df['low'].values
        c = df['close'].values
        v = df['volume'].values if 'volume' in df.columns else np.ones(len(c))
        
        # 1. Order Blocks (Supply & Demand)
        # Bullish OB: Last down candle before a sharp up move with high volume
        bullish_ob = None
        bearish_ob = None
        
        for i in range(-15, -2):
            # Check for high volume breakout
            if c[i+1] > h[i] and v[i+1] > np.mean(v[i-5:i]):
                if c[i] < o[i]: # Down candle
                    bullish_ob = {'high': h[i], 'low': l[i]}
            elif c[i+1] < l[i] and v[i+1] > np.mean(v[i-5:i]):
                if c[i] > o[i]: # Up candle
                    bearish_ob = {'high': h[i], 'low': l[i]}
        
        # 2. Fibonacci Retracement (0.618 Golden Ratio)
        recent_high = np.max(h[-30:])
        recent_low = np.min(l[-30:])
        fib_618 = recent_high - (recent_high - recent_low) * 0.618
        fib_786 = recent_high - (recent_high - recent_low) * 0.786
        
        # 3. ATR Volatility Protection
        tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
        atr = np.mean(tr[-14:])
        is_spiky = tr[-1] > atr * 2.5 # Safety Mode if current candle is too large
        
        return {
            "bullish_ob": bullish_ob,
            "bearish_ob": bearish_ob,
            "fib_618": fib_618,
            "fib_786": fib_786,
            "is_spiky": is_spiky,
            "atr": atr
        }

    def detect_5_candle_sequence(self, df: pd.DataFrame) -> Dict:
        """Analyze the last 5 candles for momentum and reversals."""
        if df is None or len(df) < 6: return {}
        
        c = df['close'].values
        o = df['open'].values
        
        last_5_colors = [1 if c[i] > o[i] else -1 for i in range(-6, -1)]
        
        sequence = "NEUTRAL"
        # 1. 4-1 Sequence (4 of one color, then a flip)
        if last_5_colors[:-1] == [1, 1, 1, 1] and last_5_colors[-1] == -1:
            sequence = "EXHAUSTION_BULLISH"
        elif last_5_colors[:-1] == [-1, -1, -1, -1] and last_5_colors[-1] == 1:
            sequence = "EXHAUSTION_BEARISH"
            
        # 2. Strong Momentum (5 in a row)
        if all(x == 1 for x in last_5_colors):
            sequence = "MOMENTUM_BULLISH"
        elif all(x == -1 for x in last_5_colors):
            sequence = "MOMENTUM_BEARISH"
            
        # 3. Micro-Range (Alternating colors)
        if last_5_colors == [1, -1, 1, -1, 1] or last_5_colors == [-1, 1, -1, 1, -1]:
            sequence = "MICRO_RANGE"

        return {"sequence": sequence}

    def generate_signal(self, symbol: str, indicators: dict, timeframe: str = '1m', df: Optional[pd.DataFrame] = None, mtf_trend: str = "NEUTRAL") -> Dict:
        # First, track outcome of previous trades
        current_price = indicators.get('current_price', 0)
        self.track_outcomes(current_price)

        smc = self.calculate_smc_patterns(df) if df is not None else {}
        inst_logic = self.detect_institutional_logic(df) if df is not None else []
        candle_patterns = self.detect_candle_patterns(df) if df is not None else []
        candle_5_logic = self.detect_5_candle_sequence(df) if df is not None else {}
        inst_zones = self.calculate_institutional_zones(df) if df is not None else {}
        
        trend_score = self.calculate_trend_score(indicators)
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        macd_sig = indicators.get('macd_signal', 0)
        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)

        signal_type = 'HOLD'
        direction = 'NONE'
        confidence = 0.0
        reasons = []

        # Volatility Protection
        if inst_zones.get("is_spiky", False):
            return {
                'symbol': symbol, 'signal': 'HOLD', 'direction': 'NONE', 'confidence': 0,
                'regime': 'VOLATILE_SAFETY', 'reasons': 'ATR Safety Mode',
                'price': current_price, 'timestamp': datetime.now().isoformat(),
                'recovery_active': self.recovery_mode, 'indicators': indicators
            }

        # Bullish Score (Max 25)
        bull_score = 0
        if trend_score > 15: bull_score += 1
        if smc.get("structure") == "BOS_UP": bull_score += 2
        if "BULLISH_HAMMER" in candle_patterns: bull_score += 2
        if "BULLISH_ENGULFING" in candle_patterns: bull_score += 2
        if "DOJI" in candle_patterns and current_price <= bb_lower: bull_score += 2.5
        
        # MTF Confluence
        if mtf_trend == "BULLISH": bull_score += 4 # High weight for MTF
        
        # Order Block Confluence
        ob_bull = inst_zones.get("bullish_ob")
        if ob_bull and current_price <= ob_bull['high'] and current_price >= ob_bull['low']:
            bull_score += 3.5 
            
        # Fibonacci Confluence
        if current_price <= inst_zones.get("fib_618", 0) or current_price <= inst_zones.get("fib_786", 0):
            bull_score += 2
            
        if "COLOR_FLIP_REVERSAL_UP" in candle_patterns: bull_score += 1.5
        if candle_5_logic.get("sequence") == "EXHAUSTION_BEARISH": bull_score += 3
        if candle_5_logic.get("sequence") == "MOMENTUM_BULLISH": bull_score += 2
        if current_price <= bb_lower: bull_score += 2 
        if rsi < 30: bull_score += 2 
        if "LIQUIDITY_GRAB_LOW" in inst_logic: bull_score += 2

        # Bearish Score (Max 25)
        bear_score = 0
        if trend_score < -15: bear_score += 1
        if smc.get("structure") == "BOS_DOWN": bear_score += 2
        if "BEARISH_STAR" in candle_patterns: bear_score += 2
        if "BEARISH_ENGULFING" in candle_patterns: bear_score += 2
        if "DOJI" in candle_patterns and current_price >= bb_upper: bear_score += 2.5
        
        # MTF Confluence
        if mtf_trend == "BEARISH": bear_score += 4
        
        # Order Block Confluence
        ob_bear = inst_zones.get("bearish_ob")
        if ob_bear and current_price >= ob_bear['low'] and current_price <= ob_bear['high']:
            bear_score += 3.5
            
        # Fibonacci Confluence
        if current_price >= inst_zones.get("fib_618", 0) or current_price >= inst_zones.get("fib_786", 0):
            bear_score += 2
            
        if "COLOR_FLIP_REVERSAL_DOWN" in candle_patterns: bear_score += 1.5
        if candle_5_logic.get("sequence") == "EXHAUSTION_BULLISH": bear_score += 3
        if candle_5_logic.get("sequence") == "MOMENTUM_BEARISH": bear_score += 2
        if current_price >= bb_upper: bear_score += 2 
        if rsi > 70: bear_score += 2 
        if "LIQUIDITY_GRAB_HIGH" in inst_logic: bear_score += 2

        # Use a lower normal threshold so live crypto scans surface signals more often.
        threshold = 6.5 if self.recovery_mode else 3.0
        
        if bull_score > bear_score and bull_score >= threshold:
            signal_type = 'BUY'
            direction = 'UP'
            base_conf = 82.0 if self.recovery_mode else 68.0
            confidence = min(99.0, base_conf + (min(bull_score, 25) * 1.2))
            reasons = [r.replace('_', ' ') for r in candle_patterns + inst_logic if "UP" in r or "LOW" in r or "BULLISH" in r]
            if mtf_trend == "BULLISH": reasons.append("MTF Trend")
            if ob_bull: reasons.append("Demand Zone")
            if current_price <= inst_zones.get("fib_618", 0): reasons.append("Fib 0.618")
            if "VELOCITY_UP" in inst_logic:
                reasons.append("Momentum")
            if not reasons:
                reasons = ["Trend + momentum alignment"]
        elif bear_score > bull_score and bear_score >= threshold:
            signal_type = 'SELL'
            direction = 'DOWN'
            base_conf = 82.0 if self.recovery_mode else 68.0
            confidence = min(99.0, base_conf + (min(bear_score, 25) * 1.2))
            reasons = [r.replace('_', ' ') for r in candle_patterns + inst_logic if "DOWN" in r or "HIGH" in r or "BEARISH" in r]
            if mtf_trend == "BEARISH": reasons.append("MTF Trend")
            if ob_bear: reasons.append("Supply Zone")
            if current_price >= inst_zones.get("fib_618", 0): reasons.append("Fib 0.618")
            if "VELOCITY_DOWN" in inst_logic:
                reasons.append("Momentum")
            if not reasons:
                reasons = ["Trend + momentum alignment"]

        # Final signal assembly
        signal = {
            'symbol': symbol,
            'signal': signal_type,
            'direction': direction,
            'confidence': round(float(confidence), 1) if signal_type != 'HOLD' else 0,
            'regime': smc.get("regime", "RANGING"),
            'reasons': ", ".join(reasons) if reasons else ("High Confluence" if signal_type != 'HOLD' else "Analyzing..."),
            'price': current_price,
            'timestamp': datetime.now().isoformat(),
            'recovery_active': self.recovery_mode,
            'indicators': indicators
        }

        self.signal_history.append(signal)
        return signal

    def get_signals_summary(self, signals: List[Dict]) -> Dict:
        if not signals: return {'buy_count': 0, 'sell_count': 0, 'hold_count': 0, 'avg_confidence': 0, 'total_signals': 0}
        buy = sum(1 for s in signals if s['signal'] == 'BUY')
        sell = sum(1 for s in signals if s['signal'] == 'SELL')
        avg_conf = np.mean([s['confidence'] for s in signals if s['signal'] != 'HOLD']) if any(s['signal'] != 'HOLD' for s in signals) else 0
        return {
            'buy_count': buy,
            'sell_count': sell,
            'hold_count': len(signals) - buy - sell,
            'avg_confidence': round(avg_conf, 1),
            'total_signals': len(signals),
            'recovery_mode': self.recovery_mode
        }
