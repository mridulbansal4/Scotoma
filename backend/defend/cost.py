"""Elkan cost matrix, expected cost, threshold optimiser, and cost_per_100k."""

from dataclasses import dataclass

import numpy as np

# Fixed operational cost of a realised fraud, on top of the transaction amount.
COST_CHARGEBACK_FEE: float = 25.0
# Gross margin lost when a good transaction is declined.
COST_MERCHANT_MARGIN: float = 0.22
# Probability a falsely declined customer does not return.
COST_P_ATTRITION: float = 0.32
# Value destroyed when that customer is lost.
COST_CUSTOMER_LTV: float = 1800.0

THRESHOLD_GRID: np.ndarray = np.linspace(0.001, 0.999, 999)
COST_SCALE_PER: float = 100_000.0


@dataclass(frozen=True)
class CostMatrix:
    chargeback_fee: float = COST_CHARGEBACK_FEE
    merchant_margin: float = COST_MERCHANT_MARGIN
    p_attrition: float = COST_P_ATTRITION
    customer_ltv: float = COST_CUSTOMER_LTV


def expected_cost(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    amounts: np.ndarray,
    matrix: CostMatrix,
) -> float:
    predicted = scores >= threshold
    false_negative = (y_true == 1) & ~predicted
    false_positive = (y_true == 0) & predicted
    fraud_loss = float(amounts[false_negative].sum())
    chargeback = matrix.chargeback_fee * int(false_negative.sum())
    margin_loss = float((amounts[false_positive] * matrix.merchant_margin).sum())
    attrition = matrix.p_attrition * matrix.customer_ltv * int(false_positive.sum())
    return fraud_loss + chargeback + margin_loss + attrition


def optimal_threshold(
    y_true: np.ndarray, scores: np.ndarray, amounts: np.ndarray, matrix: CostMatrix
) -> float:
    costs = [expected_cost(y_true, scores, t, amounts, matrix) for t in THRESHOLD_GRID]
    return float(THRESHOLD_GRID[int(np.argmin(costs))])


def cost_per_100k(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    amounts: np.ndarray,
    matrix: CostMatrix,
) -> float:
    if len(y_true) == 0:
        raise ValueError("cost_per_100k on an empty evaluation set")
    return expected_cost(y_true, scores, threshold, amounts, matrix) / len(y_true) * COST_SCALE_PER


def closed_form_threshold(amount: float, matrix: CostMatrix) -> float:
    """Elkan (2001): predict positive iff expected cost is lower, so tau* = C_FP/(C_FP+C_FN)."""
    cost_fp = amount * matrix.merchant_margin + matrix.p_attrition * matrix.customer_ltv
    cost_fn = amount + matrix.chargeback_fee
    return cost_fp / (cost_fp + cost_fn)


def matrix_from_config(config) -> CostMatrix:
    return CostMatrix(
        chargeback_fee=config.cost_chargeback_fee,
        merchant_margin=config.cost_merchant_margin,
        p_attrition=config.cost_p_attrition,
        customer_ltv=config.cost_customer_ltv,
    )
