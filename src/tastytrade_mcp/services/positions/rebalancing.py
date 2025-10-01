"""Portfolio rebalancing service."""
from decimal import Decimal
from typing import List, Dict, Any

from .models import RebalancingSuggestion


class RebalancingService:
    """Provides portfolio rebalancing recommendations."""

    def __init__(self):
        """Initialize rebalancing service."""
        pass

    async def suggest_rebalancing(
        self,
        positions: List[Dict[str, Any]],
        target_allocations: Dict[str, float],
        rebalance_threshold: float = 5.0
    ) -> Dict[str, Any]:
        """Generate rebalancing suggestions."""
        if not positions:
            return {
                "rebalancing_needed": False,
                "current_allocations": [],
                "actions": [],
                "total_trades_needed": 0
            }

        # Calculate current allocations
        total_value = sum(abs(pos.get("market_value", 0)) for pos in positions)
        if total_value == 0:
            return {
                "rebalancing_needed": False,
                "current_allocations": [],
                "actions": [],
                "total_trades_needed": 0
            }

        current_allocations = []
        actions = []
        rebalancing_needed = False

        for position in positions:
            symbol = position.get("symbol", "")
            market_value = abs(position.get("market_value", 0))
            current_percentage = (market_value / total_value) * 100
            target_percentage = target_allocations.get(symbol, 0)

            current_allocations.append({
                "symbol": symbol,
                "current_percentage": current_percentage,
                "target_percentage": target_percentage,
                "market_value": market_value
            })

            # Check if rebalancing is needed
            deviation = abs(current_percentage - target_percentage)
            if deviation >= rebalance_threshold:
                rebalancing_needed = True

                # Calculate action needed
                if current_percentage > target_percentage:
                    # Need to sell
                    excess_percentage = current_percentage - target_percentage
                    excess_value = (excess_percentage / 100) * total_value
                    actions.append({
                        "symbol": symbol,
                        "action": "sell",
                        "amount": excess_value,
                        "percentage": excess_percentage
                    })
                else:
                    # Need to buy
                    deficit_percentage = target_percentage - current_percentage
                    deficit_value = (deficit_percentage / 100) * total_value
                    actions.append({
                        "symbol": symbol,
                        "action": "buy",
                        "amount": deficit_value,
                        "percentage": deficit_percentage
                    })

        # Check for symbols in target allocation but not in current positions
        current_symbols = {pos.get("symbol", "") for pos in positions}
        for symbol, target_percentage in target_allocations.items():
            if symbol not in current_symbols and target_percentage > 0:
                rebalancing_needed = True
                target_value = (target_percentage / 100) * total_value
                actions.append({
                    "symbol": symbol,
                    "action": "buy",
                    "amount": target_value,
                    "percentage": target_percentage
                })

                current_allocations.append({
                    "symbol": symbol,
                    "current_percentage": 0,
                    "target_percentage": target_percentage,
                    "market_value": 0
                })

        return {
            "rebalancing_needed": rebalancing_needed,
            "current_allocations": current_allocations,
            "actions": actions,
            "total_trades_needed": len(actions)
        }

    def generate_rebalancing_suggestions(
        self,
        positions: List[Dict[str, Any]],
        target_allocations: Dict[str, float]
    ) -> List[RebalancingSuggestion]:
        """Generate detailed rebalancing suggestions."""
        suggestions = []

        if not positions:
            return suggestions

        total_value = sum(abs(pos.get("market_value", 0)) for pos in positions)
        if total_value == 0:
            return suggestions

        for position in positions:
            symbol = position.get("symbol", "")
            market_value = abs(position.get("market_value", 0))
            current_allocation = Decimal(str((market_value / total_value) * 100))
            target_allocation = Decimal(str(target_allocations.get(symbol, 0)))

            difference = current_allocation - target_allocation

            if abs(difference) >= 5:  # 5% threshold
                action = "SELL" if difference > 0 else "BUY"
                priority = "HIGH" if abs(difference) >= 15 else "MEDIUM" if abs(difference) >= 10 else "LOW"

                # Calculate recommended quantity (simplified)
                price_per_share = position.get("current_price", 1)
                if price_per_share > 0:
                    recommended_quantity = abs(difference) * Decimal(str(total_value)) / (100 * Decimal(str(price_per_share)))
                else:
                    recommended_quantity = Decimal("0")

                suggestions.append(RebalancingSuggestion(
                    symbol=symbol,
                    current_allocation=current_allocation,
                    target_allocation=target_allocation,
                    difference=difference,
                    action=action,
                    recommended_quantity=recommended_quantity,
                    priority=priority
                ))

        # Sort by priority and difference magnitude
        priority_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        suggestions.sort(key=lambda x: (priority_order.get(x.priority, 0), abs(x.difference)), reverse=True)

        return suggestions

    def calculate_rebalancing_costs(
        self,
        actions: List[Dict[str, Any]],
        commission_per_trade: float = 0.0,
        bid_ask_spread_bps: float = 5.0
    ) -> Dict[str, float]:
        """Calculate estimated costs for rebalancing."""
        total_commission = len(actions) * commission_per_trade
        total_spread_cost = 0

        for action in actions:
            # Estimate spread cost (simplified)
            trade_value = action.get("amount", 0)
            spread_cost = trade_value * (bid_ask_spread_bps / 10000)
            total_spread_cost += spread_cost

        return {
            "commission_costs": total_commission,
            "spread_costs": total_spread_cost,
            "total_costs": total_commission + total_spread_cost,
            "cost_percentage": ((total_commission + total_spread_cost) / sum(action.get("amount", 0) for action in actions)) * 100 if actions else 0
        }