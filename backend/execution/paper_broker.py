"""
Paper broker — simulates order execution without real money.
This is the default execution mode.
"""

import json
from typing import List, Optional
from pathlib import Path
from backend.execution.broker_base import BaseBroker, BrokerOrder, BrokerPosition
from backend.core.time_utils import now_utc, utc_timestamp, epoch_ms


class PaperBroker(BaseBroker):
    """Simulated broker for paper trading.
    Maintains account state, open positions, and fill history in memory
    and optionally persists to a JSON file.
    """

    def __init__(self, initial_balance: float = 50000.0,
                 spread: float = 0.40, data_dir: Path = None):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.peak_equity = initial_balance
        self.spread = spread
        self.positions: List[BrokerPosition] = []
        self.fills: List[dict] = []
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0
        self._data_dir = data_dir
        self._next_id = 1

        if data_dir:
            self._load_state()

    def _state_file(self) -> Optional[Path]:
        if self._data_dir:
            return self._data_dir / "paper_broker.json"
        return None

    def _save_state(self):
        f = self._state_file()
        if f:
            state = {
                "balance": self.balance,
                "initial_balance": self.initial_balance,
                "peak_equity": self.peak_equity,
                "positions": [p.to_dict() for p in self.positions],
                "fills": self.fills[-500:],
                "daily_pnl": self.daily_pnl,
                "trades_today": self.trades_today,
                "consecutive_losses": self.consecutive_losses,
                "next_id": self._next_id,
            }
            f.write_text(json.dumps(state, indent=2, default=str))

    def _load_state(self):
        f = self._state_file()
        if f and f.exists():
            try:
                state = json.loads(f.read_text())
                self.balance = state.get("balance", self.initial_balance)
                self.initial_balance = state.get("initial_balance", self.initial_balance)
                self.peak_equity = state.get("peak_equity", self.peak_equity)
                self.daily_pnl = state.get("daily_pnl", 0)
                self.trades_today = state.get("trades_today", 0)
                self.consecutive_losses = state.get("consecutive_losses", 0)
                self._next_id = state.get("next_id", 1)
                self.fills = state.get("fills", [])
                for pd in state.get("positions", []):
                    self.positions.append(BrokerPosition(
                        position_id=pd["position_id"],
                        direction=pd["direction"],
                        entry=pd["entry"],
                        stop=pd["stop"],
                        target_1=pd["target_1"],
                        target_2=pd.get("target_2"),
                        lots=pd.get("lots", 0.01),
                        strategy=pd.get("strategy", ""),
                        open_timestamp=pd.get("open_timestamp", ""),
                    ))
            except Exception:
                pass

    def submit_order(self, order: BrokerOrder) -> dict:
        """Simulate order fill with spread."""
        if order.direction == "long":
            fill_price = order.entry + self.spread / 2
        else:
            fill_price = order.entry - self.spread / 2

        pos_id = f"paper_{self._next_id}"
        self._next_id += 1

        position = BrokerPosition(
            position_id=pos_id,
            direction=order.direction,
            entry=round(fill_price, 2),
            stop=order.stop,
            target_1=order.target_1,
            target_2=order.target_2,
            lots=order.position_lots,
            strategy=order.strategy,
            open_timestamp=utc_timestamp(),
        )
        self.positions.append(position)
        self.trades_today += 1

        fill = {
            "type": "open",
            "position_id": pos_id,
            "direction": order.direction,
            "fill_price": round(fill_price, 2),
            "requested_price": order.entry,
            "slippage": round(abs(fill_price - order.entry), 2),
            "lots": order.position_lots,
            "strategy": order.strategy,
            "decision_id": order.decision_id,
            "timestamp": utc_timestamp(),
        }
        self.fills.append(fill)
        self._save_state()

        return {
            "status": "filled",
            "position_id": pos_id,
            "fill_price": round(fill_price, 2),
            "slippage": round(abs(fill_price - order.entry), 2),
        }

    def close_position(self, position_id: str, price: float = None) -> dict:
        """Close a position at the given price (or last known price)."""
        pos = None
        for p in self.positions:
            if p.position_id == position_id:
                pos = p
                break

        if not pos:
            return {"error": f"Position {position_id} not found"}

        if price is None:
            return {"error": "Price required to close paper position"}

        # Apply spread to exit
        if pos.direction == "long":
            exit_price = price - self.spread / 2
        else:
            exit_price = price + self.spread / 2

        # Compute PnL
        risk_per_oz = abs(pos.entry - pos.stop)
        oz = pos.lots * 100  # lots to oz
        if pos.direction == "long":
            pnl = (exit_price - pos.entry) * oz
            r_multiple = (exit_price - pos.entry) / risk_per_oz if risk_per_oz > 0 else 0
        else:
            pnl = (pos.entry - exit_price) * oz
            r_multiple = (pos.entry - exit_price) / risk_per_oz if risk_per_oz > 0 else 0

        self.balance += pnl
        self.daily_pnl += pnl
        equity = self.get_equity()
        if equity > self.peak_equity:
            self.peak_equity = equity

        # Track consecutive losses
        if r_multiple <= 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Remove from open positions
        self.positions = [p for p in self.positions if p.position_id != position_id]

        fill = {
            "type": "close",
            "position_id": position_id,
            "direction": pos.direction,
            "entry": pos.entry,
            "exit_price": round(exit_price, 2),
            "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2),
            "lots": pos.lots,
            "strategy": pos.strategy,
            "timestamp": utc_timestamp(),
        }
        self.fills.append(fill)
        self._save_state()

        return {
            "status": "closed",
            "position_id": position_id,
            "exit_price": round(exit_price, 2),
            "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2),
        }

    def check_stops_and_targets(self, current_price: float) -> List[dict]:
        """Check all open positions for stop loss and target hits.
        Returns list of closed position results.
        """
        results = []
        to_close = []

        for pos in self.positions:
            if pos.direction == "long":
                if current_price <= pos.stop:
                    to_close.append((pos.position_id, pos.stop, "stop_loss"))
                elif current_price >= pos.target_1:
                    to_close.append((pos.position_id, pos.target_1, "target_1"))
            else:
                if current_price >= pos.stop:
                    to_close.append((pos.position_id, pos.stop, "stop_loss"))
                elif current_price <= pos.target_1:
                    to_close.append((pos.position_id, pos.target_1, "target_1"))

        for pid, price, reason in to_close:
            result = self.close_position(pid, price)
            result["exit_reason"] = reason
            results.append(result)

        return results

    def update_unrealized(self, current_price: float):
        """Update unrealized PnL on all open positions."""
        for pos in self.positions:
            oz = pos.lots * 100
            if pos.direction == "long":
                pos.unrealized_pnl = (current_price - pos.entry) * oz
            else:
                pos.unrealized_pnl = (pos.entry - current_price) * oz

    def get_equity(self) -> float:
        """Balance + unrealized PnL."""
        unrealized = sum(p.unrealized_pnl for p in self.positions)
        return round(self.balance + unrealized, 2)

    def get_positions(self) -> List[BrokerPosition]:
        return self.positions

    def get_account(self) -> dict:
        equity = self.get_equity()
        unrealized = sum(p.unrealized_pnl for p in self.positions)
        drawdown_pct = ((self.peak_equity - equity) / self.peak_equity * 100
                        if self.peak_equity > 0 else 0)
        return {
            "balance": round(self.balance, 2),
            "equity": round(equity, 2),
            "unrealized_pnl": round(unrealized, 2),
            "peak_equity": round(self.peak_equity, 2),
            "drawdown_pct": round(drawdown_pct, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "open_positions": len(self.positions),
            "trades_today": self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "initial_balance": self.initial_balance,
            "mode": "paper",
        }

    def get_fills(self, limit: int = 50) -> List[dict]:
        return self.fills[-limit:]

    def is_live(self) -> bool:
        return False

    def reset_daily(self):
        """Reset daily counters (call at start of new trading day)."""
        self.daily_pnl = 0.0
        self.trades_today = 0
        self._save_state()

    def get_account_features(self) -> dict:
        """Return account state as features for the feature engine."""
        account = self.get_account()
        return {
            "open_positions": account["open_positions"],
            "unrealized_pnl": account["unrealized_pnl"],
            "current_drawdown_pct": account["drawdown_pct"],
            "daily_pnl": account["daily_pnl"],
            "equity": account["equity"],
            "peak_equity": account["peak_equity"],
            "trades_today": account["trades_today"],
            "consecutive_losses": account["consecutive_losses"],
        }
