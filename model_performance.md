# Fraud Detection Model Performance Report

This document outlines the evolutionary performance of the three distinct machine learning models trained during this project. 

The primary objective was to maximize **Recall** (catching as much fraud as possible) while significantly boosting **Precision** (minimizing false positives to reduce analyst fatigue).

---

## 1. Baseline Model: Logistic Regression
The Logistic Regression model served as our initial baseline. To combat the severe class imbalance, class weights were aggressively balanced.

*   **ROC AUC**: 0.9960
*   **PR AUC**: 0.6299
*   **Precision**: 24.63% (0.2463)
*   **Recall**: 98.10% (0.9810)
*   **F1-Score**: 0.3937

**Analysis**: While the model successfully caught almost all fraud (98.1% Recall), it suffered from an unacceptably low precision. Only 1 in 4 flagged transactions was actual fraud, meaning analysts would be overwhelmed with false positives.

---

## 2. Intermediate Model: Random Forest
We transitioned to a tree-based ensemble to capture non-linear relationships and complex interactions between behavioral features (like velocity and z-scores) that linear models miss.

*   **Precision**: 67.42% (0.6742)
*   **Recall**: 95.55% (0.9555)
*   **F1-Score**: 0.7906

**Analysis**: This was a massive leap forward. By using a Random Forest, precision nearly tripled (from 24% to 67%), drastically cutting down false positives. Recall dipped slightly but remained highly robust at ~95.5%.

---

## 3. Champion Model: XGBoost
For our final production model, we utilized Extreme Gradient Boosting (XGBoost). By iteratively correcting the errors of previous trees, XGBoost was able to pinpoint elusive fraud patterns (like low-value evasive fraud) with surgical precision.

*   **ROC AUC**: 0.9996
*   **PR AUC**: 0.9618
*   **Precision**: 84.03% (0.8403)
*   **Recall**: 93.29% (0.9329)
*   **F1-Score**: 0.8842

**Analysis**: XGBoost emerged as our absolute champion. It achieved an exceptional **84% Precision** while still catching **93.2% of all fraud**. The PR AUC score (0.9618) proves its extreme robustness on highly imbalanced data. This model provides the perfect balance for a production environment: minimizing analyst alert fatigue while aggressively protecting customer assets.

### Why We Chose XGBoost Over Random Forest
While Random Forest provided a massive leap over the baseline, we still advanced to XGBoost for several critical reasons:
1. **Iterative Error Correction**: Unlike Random Forest which builds trees independently (bagging), XGBoost builds trees sequentially (boosting), where each new tree specifically focuses on correcting the errors of the previous ones. This makes it far superior at catching borderline, evasive fraud.
2. **Alert Fatigue (Precision)**: In fraud operations, human analyst time is the most expensive resource. XGBoost boosted our Precision from 67% to 84%. In a real-world scenario, this means eliminating thousands of false alarms per day, allowing the fraud team to focus only on genuine threats.
3. **Handling Extreme Imbalance**: XGBoost's `scale_pos_weight` parameter provides mathematically superior handling of our highly skewed dataset (where legitimate transactions vastly outnumber fraud) compared to Random Forest's class weighting.
