"""Options-play blueprints for bullish stock setups.

Twelve Data's free tier has no option chains, greeks, or implied vol, so Python
cannot price a contract. Instead — mirroring the repo's tier split — it emits the
deterministic *structure* of the trade and leaves live pricing + execution to the
routine agent (Robinhood MCP):

  Python here  → strategy, expiration window, target strike/delta, premium budget,
                 and the planned exit (tied to the underlying's technical stop).
  Routine agent → get_option_chains / get_option_quotes to find the real contract
                 nearest these targets, verify liquidity + affordability, then
                 review_option_order → place_option_order.

The default structure is a slightly-in-the-money LONG CALL at the breakout pivot:
defined risk (max loss = premium paid), real leverage for a tiny account that
often can't buy a meaningful share count of a higher-priced leader, and far less
theta bleed than a cheap OTM call. The thesis is the same Stage 2 breakout as the
share order — so the exit is the same too: close the call if the underlying loses
its stop, not at expiry.
"""

from config import (
    ACCOUNT_SIZE,
    OPTIONS_ENABLED,
    OPTIONS_MIN_DTE,
    OPTIONS_TARGET_DTE,
    OPTIONS_MAX_DTE,
    OPTIONS_TARGET_DELTA,
    OPTIONS_MAX_PREMIUM_PCT,
    OPTIONS_MAX_SPREAD_PCT,
)


def build_options_play(
    entry: float,
    stop: float,
    t1: float | None,
    t2: float | None,
    price: float,
    account_size: float = ACCOUNT_SIZE,
    cash_available: float | None = None,
) -> dict | None:
    """Return an options blueprint for a bullish setup, or None if disabled/invalid.

    `entry` is the breakout pivot (also the share order's limit price); `stop` is
    the underlying technical stop. The premium budget is capped at the lesser of
    OPTIONS_MAX_PREMIUM_PCT of the account and the cash actually available, so the
    agent never sizes a position the account can't fund.
    """
    if not OPTIONS_ENABLED:
        return None
    if not entry or entry <= 0 or not stop or stop >= entry:
        return None

    premium_budget = account_size * OPTIONS_MAX_PREMIUM_PCT
    if cash_available is not None:
        premium_budget = min(premium_budget, cash_available)
    if premium_budget <= 0:
        return None

    return {
        "strategy": "long_call",
        "direction": "bullish",
        "underlying_entry_ref": round(entry, 2),
        "underlying_stop_ref": round(stop, 2),
        "underlying_price_now": round(price, 2),
        "expiry": {
            "target_dte": OPTIONS_TARGET_DTE,
            "min_dte": OPTIONS_MIN_DTE,
            "max_dte": OPTIONS_MAX_DTE,
        },
        "strike": {
            "target_strike": round(entry, 2),  # ATM at the breakout pivot
            "target_delta": OPTIONS_TARGET_DELTA,
            "guidance": (
                "Pick the call nearest the breakout pivot strike / ~"
                f"{OPTIONS_TARGET_DELTA} delta (slightly ITM). Slightly-ITM beats "
                "cheap OTM here: more delta, less theta, holds value through the swing."
            ),
        },
        "max_premium_dollars": round(premium_budget, 2),
        "max_premium_pct_of_account": OPTIONS_MAX_PREMIUM_PCT,
        "sizing_rule": (
            "contracts = floor(max_premium_dollars / (ask * 100)); place 0 orders "
            "if even 1 contract exceeds max_premium_dollars."
        ),
        "defined_risk_note": (
            "Max loss = total premium paid. Count that full premium toward "
            "EXISTING_RISK / the 6% portfolio-heat cap on subsequent runs."
        ),
        "exit_rule": (
            f"Close the call if the underlying breaks its stop ${round(stop, 2)} "
            "(thesis invalidated) — manage by the STOCK's technical levels, not by "
            "option expiry. Take profits as the underlying reaches its targets."
        ),
        "profit_target_ref": {
            "underlying_t1": round(t1, 2) if t1 else None,
            "underlying_t2": round(t2, 2) if t2 else None,
        },
        "liquidity_gate": {
            "max_bid_ask_spread_pct_of_mid": OPTIONS_MAX_SPREAD_PCT,
            "note": (
                "Skip contracts with a bid/ask spread wider than "
                f"{int(OPTIONS_MAX_SPREAD_PCT * 100)}% of mid, or with near-zero "
                "open interest / volume — a tiny account can't exit those cleanly."
            ),
        },
        "agent_instructions": (
            "1) get_option_chains for this ticker. "
            f"2) Filter to an expiration {OPTIONS_MIN_DTE}-{OPTIONS_MAX_DTE} DTE "
            f"(target ~{OPTIONS_TARGET_DTE}). "
            f"3) Pick the CALL nearest delta {OPTIONS_TARGET_DELTA} / strike "
            f"${round(entry, 2)}. "
            "4) get_option_quotes to price it and check the spread/liquidity gate. "
            "5) Size contracts within max_premium_dollars. "
            "6) review_option_order BEFORE place_option_order. "
            "7) Record the premium as risk for the heat cap; plan to close on the "
            "underlying stop break."
        ),
    }
