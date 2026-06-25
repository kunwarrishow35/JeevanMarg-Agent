"""Trust MCP Server — provides corridor trust score calculation via MCP protocol.

This is a real FastMCP server that exposes tools for trust score computation.
Agents call these tools through the MCP protocol, NOT through direct function calls.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from app.config import settings

mcp = FastMCP(
    name="TrustMCPServer",
    instructions="Trust score MCP server for JeevanMarg emergency corridor system. "
                 "Calculates corridor trust scores using weighted multi-factor analysis.",
)


# Trust score weights
WEIGHTS = {
    "congestion": 0.25,
    "route_stability": 0.20,
    "traffic_volatility": 0.20,
    "corridor_continuity": 0.20,
    "eta_confidence": 0.15,
}


@mcp.tool()
def calculate_trust_score(
    congestion_score: float,
    route_stability_score: float,
    traffic_volatility_score: float,
    corridor_continuity_score: float,
    eta_confidence_score: float,
) -> str:
    """Calculate corridor trust score from weighted factors.

    Each factor should be a score from 0.0 (worst) to 1.0 (best).
    The trust score is computed as a weighted average scaled to 0-100.

    Scoring bands:
    - 90-100: Excellent (corridor fully reliable)
    - 70-89: Healthy (corridor reliable with minor concerns)
    - 50-69: Warning (corridor degrading, intervention may be needed)
    - 0-49: Critical (corridor unreliable, immediate action required)

    Args:
        congestion_score: Inverse congestion (1.0 = no congestion, 0.0 = fully congested).
        route_stability_score: Route stability (1.0 = very stable, 0.0 = unstable).
        traffic_volatility_score: Inverse volatility (1.0 = stable traffic, 0.0 = highly volatile).
        corridor_continuity_score: Corridor continuity (1.0 = no gaps, 0.0 = broken corridor).
        eta_confidence_score: ETA prediction confidence (1.0 = high confidence, 0.0 = low confidence).

    Returns:
        JSON string with trust score (0-100), trust level, corridor health,
        factor breakdown, and recommendations.
    """
    factors = {
        "congestion": max(0.0, min(1.0, congestion_score)),
        "route_stability": max(0.0, min(1.0, route_stability_score)),
        "traffic_volatility": max(0.0, min(1.0, traffic_volatility_score)),
        "corridor_continuity": max(0.0, min(1.0, corridor_continuity_score)),
        "eta_confidence": max(0.0, min(1.0, eta_confidence_score)),
    }

    # Weighted trust score
    raw_score = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
    trust_score = round(raw_score * 100, 1)

    # Determine trust level
    if trust_score >= 90:
        trust_level = "excellent"
        recommendation = "Corridor is fully reliable. No intervention needed."
    elif trust_score >= 70:
        trust_level = "healthy"
        recommendation = "Corridor is reliable with minor concerns. Monitor for changes."
    elif trust_score >= 50:
        trust_level = "warning"
        recommendation = "Corridor is degrading. Consider activating recovery protocols."
    else:
        trust_level = "critical"
        recommendation = "Corridor is unreliable. Immediate recovery action required."

    # Corridor health (slightly different weighting emphasizing continuity)
    corridor_health = round(
        (factors["corridor_continuity"] * 0.4 +
         factors["congestion"] * 0.3 +
         factors["route_stability"] * 0.3) * 100, 1
    )

    return json.dumps({
        "trust_score": trust_score,
        "trust_level": trust_level,
        "corridor_health": corridor_health,
        "eta_confidence": round(factors["eta_confidence"] * 100, 1),
        "factors": {k: round(v * 100, 1) for k, v in factors.items()},
        "weights": {k: round(v * 100, 0) for k, v in WEIGHTS.items()},
        "recommendation": recommendation,
        "requires_recovery": trust_score < (65 if settings.DEMO_MODE else 70),
    }, indent=2)


@mcp.tool()
def assess_reliability(trust_score: float, trend: str = "stable") -> str:
    """Assess overall corridor reliability and recommend action level.

    Evaluates the corridor's operational reliability based on the trust score
    and its recent trend (improving, stable, or degrading).

    Args:
        trust_score: Current trust score (0-100).
        trend: Score trend - 'improving', 'stable', or 'degrading'.

    Returns:
        JSON string with reliability assessment, action level, and detailed analysis.
    """
    # Determine reliability rating
    threshold = 65 if settings.DEMO_MODE else 70
    if trust_score >= 90:
        reliability = "high"
        action_level = "none"
        analysis = "Emergency corridor is operating at peak reliability. All factors within optimal range."
    elif trust_score >= threshold:
        reliability = "moderate"
        action_level = "monitor"
        analysis = "Corridor is functional but showing some stress factors. Continuous monitoring recommended."
    elif trust_score >= 50:
        reliability = "low"
        action_level = "intervene"
        analysis = f"Corridor reliability has dropped below acceptable threshold ({threshold}). Recovery planning should begin immediately."
    else:
        reliability = "critical"
        action_level = "emergency"
        analysis = "Corridor is unreliable for emergency transport. Alternative routing required urgently."

    # Adjust based on trend
    if trend == "degrading" and trust_score < (threshold + 10):
        action_level = "intervene" if action_level == "monitor" else action_level
        analysis += " Trend is degrading, which compounds the concern."
    elif trend == "improving" and trust_score >= 50:
        analysis += " Positive trend detected — situation may stabilize."

    return json.dumps({
        "trust_score": trust_score,
        "reliability": reliability,
        "action_level": action_level,
        "trend": trend,
        "analysis": analysis,
        "should_activate_recovery": action_level in ("intervene", "emergency"),
        "priority": "critical" if action_level == "emergency" else
                    "high" if action_level == "intervene" else
                    "normal",
    }, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
