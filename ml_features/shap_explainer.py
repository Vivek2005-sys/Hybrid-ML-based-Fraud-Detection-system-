from typing import List, Dict, Any

FEATURE_TRANSLATIONS = {
    'amount': 'the sheer size of the transaction',
    'is_active_vpn': 'the use of an active VPN',
    'is_international': 'it being an international transaction',
    'minutes_since_last_txn_clean': 'the rapid timing since their last purchase',
    'gap_volatility_5tx_clean': 'an unusual burst of rapid-fire transactions',
    'amount_z_score': 'the amount being a massive spike compared to their normal personal spending habits',
    'merchant_diversity_7d': 'shopping at an unusual number of different merchants recently',
    'hour_of_day': 'the transaction occurring at a suspicious time of day',
    'is_night_txn': 'it occurring very late at night',
    'is_high_risk_category': 'the purchase being in a high-risk category (like Electronics or Travel)',
    'p7d_txn_count': 'an unusual amount of recent account activity',
    'p7d_avg_amount': 'their recent 7-day average spend',
    'p7d_sum_amount': 'their recent 7-day total spending',
    'p7d_std_amount': 'highly erratic spending patterns over the last week',
    'p30d_txn_count': 'their 30-day transaction volume',
    'p30d_avg_amount': 'their historical 30-day average spend',
    'p30d_sum_amount': 'their historical 30-day total spend',
    'p30d_std_amount': 'their long-term spending variance',
    'p90d_txn_count': 'their 90-day transaction volume',
    'p90d_avg_amount': 'their long-term 90-day average spend'
}

def generate_explanation(explainer, X_input, feature_cols: List[str], ml_score: float, decision_threshold: float = 0.20) -> tuple[List[Dict[str, Any]], str]:
    """
    Computes SHAP values for the transaction, extracts top contributing features,
    and builds a plain-English narrative explanation.
    """
    ml_explanation = []
    ml_narrative = "Explainability skipped or encountered an error."
    
    if explainer is None:
        return ml_explanation, ml_narrative
        
    try:
        # Calculate SHAP values for the transaction
        shap_values = explainer.shap_values(X_input)
        
        # XGBoost SHAP output shape handling
        if isinstance(shap_values, list):
            shap_vals = shap_values[1][0]  # Get probability of fraud (class 1)
        else:
            if len(shap_values.shape) == 2:
                shap_vals = shap_values[0] # Single row
            else:
                shap_vals = shap_values[0, :, 1] if len(shap_values.shape) > 2 and shap_values.shape[2] == 2 else shap_values[0]

        # Create a list of (feature_name, shap_value)
        feature_contributions = list(zip(feature_cols, shap_vals))
        
        # Sort by absolute impact (highest positive or negative impact)
        feature_contributions.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # Get the top 3 driving features
        top_positive = []
        top_negative = []
        for feature, impact in feature_contributions[:3]:
            direction = "increased" if impact > 0 else "decreased"
            ml_explanation.append({
                "feature": feature,
                "impact_value": float(impact),
                "description": f"{feature} {direction} fraud risk"
            })
            if impact > 0:
                top_positive.append(feature)
            else:
                top_negative.append(feature)

        # Build Plain English Narrative
        ml_narrative = "The AI model evaluated the transaction as normal based on standard account behavior."
        
        if ml_score >= decision_threshold and top_positive:
            reasons = [FEATURE_TRANSLATIONS.get(f, f"unusual behavior in {f}") for f in top_positive]
            if len(reasons) > 1:
                reasons_str = ", ".join(reasons[:-1]) + ", and " + reasons[-1]
            else:
                reasons_str = reasons[0]
            ml_narrative = f"The AI model flagged this transaction as highly suspicious primarily due to {reasons_str}."
            
        elif ml_score < decision_threshold and top_negative:
            reasons = [FEATURE_TRANSLATIONS.get(f, f"normal {f}") for f in top_negative]
            if len(reasons) > 1:
                reasons_str = ", ".join(reasons[:-1]) + ", and " + reasons[-1]
            else:
                reasons_str = reasons[0]
            ml_narrative = f"The AI model considered this transaction safe, largely because {reasons_str} aligned with normal trusted patterns."

    except Exception as e:
        ml_explanation = [{"error": f"SHAP explanation failed: {str(e)}"}]
        ml_narrative = "Explainability engine encountered an error."

    return ml_explanation, ml_narrative
