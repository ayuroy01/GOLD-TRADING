"""
Broker adapter interface.
All execution (paper and live) goes through this interface.
"""

import abc
from typing import List, Optional


class BrokerOrder:
    """Represents an order submitted to a broker."""

    def __init__(self, direction: str, entry: float, stop: float,
                 target_1: float, target_2: float = None,
                 position_lots: float = 0.01, strategy: str = "",
                 decision_id: str = ""):
        self.direction = direction
        self.entry = entry
        self.stop = stop
        self.target_1 = target_1
        self.target_2 = target_2
        self.position_lots = position_lots
        self.strategy = strategy
        self.decision_id = decision_id

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "entry": self.entry,
            "stop": self.stop,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "position_lots": self.position_lots,
            "strategy": self.strategy,
            "decision_id": self.decision_id,
        }


class BrokerPosition:
    """Represents an open position."""

    def __init__(self, position_id: str, direction: str, entry: float,
                 stop: float, target_1: float, target_2: float = None,
                 lots: float = 0.01, strategy: str = "",
                 open_timestamp: str = "", unrealized_pnl: float = 0):
        self.position_id = position_id
        self.direction = direction
        self.entry = entry
        self.stop = stop
        self.target_1 = target_1
        self.target_2 = target_2
        self.lots = lots
        self.strategy = strategy
        self.open_timestamp = open_timestamp
        self.unrealized_pnl = unrealized_pnl

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "direction": self.direction,
            "entry": self.entry,
            "stop": self.stop,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "lots": self.lots,
            "strategy": self.strategy,
            "open_timestamp": self.open_timestamp,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
        }


class BaseBroker(abc.ABC):
    """Abstract broker interface for all execution adapters."""

    @abc.abstractmethod
    def submit_order(self, order: BrokerOrder) -> dict:
        """Submit an order. Returns {order_id, status, fill_price, ...}"""

    @abc.abstractmethod
    def close_position(self, position_id: str, price: float = None) -> dict:
        """Close a position. Returns {position_id, exit_price, pnl, ...}"""

    @abc.abstractmethod
    def get_positions(self) -> List[BrokerPosition]:
        """Get all open positions."""

    @abc.abstractmethod
    def get_account(self) -> dict:
        """Get account state: {balance, equity, unrealized_pnl, margin_used}"""

    @abc.abstractmethod
    def get_fills(self, limit: int = 50) -> List[dict]:
        """Get recent fills/executions."""

    @abc.abstractmethod
    def is_live(self) -> bool:
        """Whether this broker executes real orders."""
