"""
Statistical Analysis: Calculates p-values and significance from permutation test results.
"""
import numpy as np
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PermutationTestResult:
    """Container for permutation test results."""
    original_score: float
    permuted_scores: List[float]
    p_value: float
    is_significant: bool
    alpha: float
    n_permutations: int
    metric_name: str
    
    # Derived statistics
    permuted_mean: float
    permuted_std: float
    percentile: float  # What percentile the original score falls at


def calculate_p_value(original_score: float, permuted_scores: List[float]) -> float:
    """
    Calculate the one-tailed p-value for permutation test.
    
    Formula: p = (N_better + 1) / (M + 1)
    
    Where:
    - N_better = number of permuted scores >= original score
    - M = total number of permutations
    
    This tests the null hypothesis that the original score could have 
    arisen by chance from the null distribution.
    
    Args:
        original_score: The score from the original (un-shuffled) data
        permuted_scores: List of scores from permuted data
        
    Returns:
        P-value (0 to 1)
    """
    if len(permuted_scores) == 0:
        return 1.0
    
    scores = np.array(permuted_scores)
    n_better = np.sum(scores >= original_score)
    m = len(scores)
    
    p_value = (n_better + 1) / (m + 1)
    return p_value


def calculate_percentile(original_score: float, permuted_scores: List[float]) -> float:
    """
    Calculate what percentile the original score falls at in the null distribution.
    
    Args:
        original_score: The score from original data
        permuted_scores: List of scores from permuted data
        
    Returns:
        Percentile (0 to 100)
    """
    if len(permuted_scores) == 0:
        return 50.0
    
    scores = np.array(permuted_scores)
    percentile = 100 * np.sum(scores < original_score) / len(scores)
    return percentile


def analyze_permutation_results(
    original_score: float,
    permuted_scores: List[float],
    metric_name: str = 'sharpe',
    alpha: float = 0.05
) -> PermutationTestResult:
    """
    Analyze permutation test results and determine significance.
    
    Args:
        original_score: Score from original data
        permuted_scores: List of scores from permutations
        metric_name: Name of the metric being tested
        alpha: Significance level (default 0.05)
        
    Returns:
        PermutationTestResult with all statistics
    """
    p_value = calculate_p_value(original_score, permuted_scores)
    is_significant = p_value < alpha
    
    scores = np.array(permuted_scores) if permuted_scores else np.array([0.0])
    
    result = PermutationTestResult(
        original_score=original_score,
        permuted_scores=permuted_scores,
        p_value=p_value,
        is_significant=is_significant,
        alpha=alpha,
        n_permutations=len(permuted_scores),
        metric_name=metric_name,
        permuted_mean=float(np.mean(scores)),
        permuted_std=float(np.std(scores)),
        percentile=calculate_percentile(original_score, permuted_scores)
    )
    
    logger.info(
        f"Permutation Test Results:\n"
        f"  Original {metric_name}: {original_score:.4f}\n"
        f"  Permuted Mean: {result.permuted_mean:.4f} (std: {result.permuted_std:.4f})\n"
        f"  P-Value: {p_value:.4f}\n"
        f"  Significant (alpha={alpha}): {is_significant}\n"
        f"  Percentile: {result.percentile:.1f}%"
    )
    
    return result


def generate_histogram_data(
    permuted_scores: List[float],
    original_score: float,
    n_bins: int = 30
) -> Dict[str, Any]:
    """
    Generate histogram data for frontend visualization.
    
    Args:
        permuted_scores: List of permuted scores
        original_score: The original score (for marker)
        n_bins: Number of histogram bins
        
    Returns:
        Dict with 'bins', 'counts', and 'original_score'
    """
    if len(permuted_scores) == 0:
        return {
            'bins': [],
            'counts': [],
            'original_score': original_score
        }
    
    scores = np.array(permuted_scores)
    counts, bin_edges = np.histogram(scores, bins=n_bins)
    
    # Convert to list of {x: bin_center, y: count}
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    return {
        'bins': bin_centers.tolist(),
        'counts': counts.tolist(),
        'bin_edges': bin_edges.tolist(),
        'original_score': original_score
    }
