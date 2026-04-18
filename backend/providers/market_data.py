"""
Market data provider interface and implementations.
Provides OHLC candles, live quotes, and historical data for XAU/USD.
"""

import abc
import hashlib
import math
import random
from typing import List, Optional
from backend.core.time_utils import now_utc, utc_timestamp, to_utc, get_session, UTC
from backend.core.schemas import Timeframe, validate_candle
import datetime


class MarketDataProvider(abc.ABC):
    """Abstract interface for market data providers."""

    @abc.abstractmethod
    def get_quote(self) -> dict:
        """Get current price quote.
        Returns: {price, bid, ask, spread, timestamp, source}
        """

    @abc.abstractmethod
    def get_candles(self, timeframe: str, count: int = 100,
                    end_time: datetime.datetime = None) -> List[dict]:
        """Get historical OHLC candles.
        Returns list of {timestamp, open, high, low, close, volume, timeframe}
        """

    @abc.abstractmethod
    def get_spread(self) -> float:
        """Get current typical spread in price units."""

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize gold symbol variations."""
        s = symbol.upper().replace("/", "").replace(" ", "")
        if s in ("XAUUSD", "GOLDUSD", "GOLD"):
            return "XAUUSD"
        return s


class SimulatedMarketDataProvider(MarketDataProvider):
    """Simulated market data provider for offline development and backtesting.
    Generates deterministic, realistic-looking XAU/USD data based on time hashing.
    """

    def __init__(self, base_price: float = 3250.0, volatility: float = 0.002):
        self.base_price = base_price
        self.volatility = volatility

    def _hash_seed(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def get_quote(self) -> dict:
        now = now_utc()
        seed = self._hash_seed(now.strftime("%Y-%m-%d-%H-%M") + "q")
        variation = ((seed % 10000) - 5000) / 100
        price = round(self.base_price + variation, 2)
        spread = round(0.30 + (seed % 50) / 100, 2)
        return {
            "price": price,
            "bid": round(price - spread / 2, 2),
            "ask": round(price + spread / 2, 2),
            "spread": spread,
            "timestamp": utc_timestamp(),
            "source": "simulated",
            "session": get_session(now),
        }

    def get_candles(self, timeframe: str = "1h", count: int = 100,
                    end_time: datetime.datetime = None) -> List[dict]:
        tf_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440
        }
        minutes = tf_minutes.get(timeframe, 60)
        if end_time is None:
            end_time = now_utc()
        end_time = to_utc(end_time)

        candles = []
        price = self.base_price
        rng = random.Random(42)

        start_time = end_time - datetime.timedelta(minutes=minutes * count)

        for i in range(count):
            ts = start_time + datetime.timedelta(minutes=minutes * i)
            seed = self._hash_seed(ts.isoformat() + timeframe)

            drift = (seed % 200 - 100) / 10000
            vol = self.volatility * math.sqrt(minutes / 60)

            o = price
            moves = [rng.gauss(drift, vol) for _ in range(4)]
            prices = [o]
            p = o
            for m in moves:
                p = p * (1 + m)
                prices.append(p)
            c = prices[-1]
            h = max(prices)
            l = min(prices)

            candle = {
                "timestamp": ts.isoformat(),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": seed % 5000 + 500,
                "timeframe": timeframe,
            }
            candles.append(candle)
            price = c

        return candles

    def get_spread(self) -> float:
        quote = self.get_quote()
        return quote["spread"]


class HistoricalReplayProvider(MarketDataProvider):
    """Replays pre-loaded historical candle data.
    Used for backtesting - feeds candles one at a time in chronological order.
    """

    def __init__(self, candles: List[dict]):
        """Initialize with a list of candle dicts sorted by timestamp."""
        self._candles = sorted(candles, key=lambda c: c["timestamp"])
        self._index = 0
        self._current_price = candles[0]["close"] if candles else 3250.0

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def total_candles(self) -> int:
        return len(self._candles)

    def advance(self) -> Optional[dict]:
        """Move to the next candle. Returns it or None if exhausted."""
        if self._index >= len(self._candles):
            return None
        candle = self._candles[self._index]
        self._current_price = candle["close"]
        self._index += 1
        return candle

    def peek(self) -> Optional[dict]:
        """Look at current candle without advancing."""
        if self._index >= len(self._candles):
            return None
        return self._candles[self._index]

    def reset(self):
        """Reset to the beginning."""
        self._index = 0
        if self._candles:
            self._current_price = self._candles[0]["close"]

    def get_quote(self) -> dict:
        price = self._current_price
        spread = 0.40
        return {
            "price": round(price, 2),
            "bid": round(price - spread / 2, 2),
            "ask": round(price + spread / 2, 2),
            "spread": spread,
            "timestamp": self._candles[min(self._index, len(self._candles) - 1)]["timestamp"] if self._candles else utc_timestamp(),
            "source": "historical_replay",
        }

    def get_candles(self, timeframe: str = "1h", count: int = 100,
                    end_time: datetime.datetime = None) -> List[dict]:
        """Return candles up to the current replay index (no lookahead)."""
        available = self._candles[:self._index]
        return available[-count:]

    def get_spread(self) -> float:
        return 0.40
