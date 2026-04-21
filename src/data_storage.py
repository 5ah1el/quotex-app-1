import os
import json
from datetime import datetime
from typing import Dict, List, Optional

class DataStorage:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.prices_file = os.path.join(data_dir, "prices.csv")
        self.signals_file = os.path.join(data_dir, "signals.json")
        self.price_cache: Dict[str, List] = {}
        self.signal_cache: List[Dict] = []

    def save_price(self, symbol: str, price: float, timestamp: Optional[str] = None):
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        if symbol not in self.price_cache:
            self.price_cache[symbol] = []

        self.price_cache[symbol].append({
            'symbol': symbol,
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only last 1000 prices in memory to prevent leak
        if len(self.price_cache[symbol]) > 1000:
            self.price_cache[symbol].pop(0)

    def save_signal(self, signal: Dict):
        # Always save signals as they are important
        self.signal_cache.append(signal)
        if len(self.signal_cache) > 500:
            self.signal_cache.pop(0)

        try:
            with open(self.signals_file, 'w') as f:
                json.dump(self.signal_cache, f, indent=2)
        except Exception as e:
            print(f"Error saving signals: {e}")

    def update_signal_result(self, signal_id: str, result: str):
        updated = False
        for signal in self.signal_cache:
            if signal.get("signal_id") == signal_id:
                signal["manual_result"] = result
                updated = True
                break

        if not updated:
            return

        try:
            with open(self.signals_file, 'w') as f:
                json.dump(self.signal_cache, f, indent=2)
        except Exception as e:
            print(f"Error updating signal result: {e}")

    def get_historical_prices(self, symbol: str, limit: int = 100) -> List[Dict]:
        return self.price_cache.get(symbol, [])[-limit:]

    def get_signal_history(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict]:
        if symbol:
            return [s for s in self.signal_cache if s.get('symbol') == symbol][-limit:]
        return self.signal_cache[-limit:]

    def clear_cache(self):
        self.price_cache = {}
        self.signal_cache = []
        try:
            with open(self.signals_file, 'w') as f:
                json.dump([], f, indent=2)
            with open(self.prices_file, 'w') as f:
                f.write("symbol,price,timestamp\n")
        except Exception as e:
            print(f"Error clearing cache: {e}")
