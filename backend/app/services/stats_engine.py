import numpy as np
import scipy.stats as stats

class StatsEngine:
    """
    Person 2's Domain:
    Protects the LLM from hallucinating math. Use traditional 
    libraries (NumPy, SciPy) to calculate statistical insights.
    """
    
    @staticmethod
    def calculate_drift(data_points: list) -> dict:
        """
        Check for trend in time-series data using linear regression.
        Returns slope, direction, and p-value.
        """
        if len(data_points) < 2:
            return {"error": "Not enough data points to calculate drift."}
            
        x = np.arange(len(data_points))
        y = np.array(data_points)
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"
        
        return {
            "slope": round(float(slope), 4),
            "trend": direction,
            "p_value": round(float(p_value), 4),
            "is_significant": p_value < 0.05
        }
    
    @staticmethod
    def find_anomalies(data_points: list, threshold: float = 2.0) -> list:
        """
        Identify values that deviate from the mean by more than `threshold` standard deviations (z-score).
        Returns a list of dictionaries with index, value, and z_score.
        """
        if not data_points:
            return []
            
        y = np.array(data_points)
        z_scores = np.abs(stats.zscore(y))
        
        anomalies = []
        for i, z in enumerate(z_scores):
            if z > threshold:
                anomalies.append({
                    "index": i,
                    "value": float(y[i]),
                    "z_score": round(float(z), 2)
                })
        return anomalies
        
    @staticmethod
    def compare_means(group1: list, group2: list) -> dict:
        """
        Compare two machines or batches using a Welch's t-test (handles unequal variances).
        Returns the means, difference, and whether the difference is statistically significant.
        """
        if not group1 or not group2:
            return {"error": "Missing data for one or both groups."}
            
        mean1 = np.mean(group1)
        mean2 = np.mean(group2)
        diff = mean1 - mean2
        
        # Welch's t-test
        t_stat, p_value = stats.ttest_ind(group1, group2, equal_var=False)
        
        return {
            "mean_group_1": round(float(mean1), 4),
            "mean_group_2": round(float(mean2), 4),
            "difference": round(float(diff), 4),
            "p_value": round(float(p_value), 4),
            "is_significant": p_value < 0.05
        }

    @staticmethod
    def compute_correlation(x_series: list, y_series: list) -> dict:
        """
        Compute Pearson correlation between two numeric series.
        Returns r, p-value, strength label, and plain-English interpretation.
        """
        if len(x_series) < 3 or len(y_series) < 3:
            return {"error": "Insufficient data for correlation (need >= 3 points)."}

        n = min(len(x_series), len(y_series))
        x = np.array(x_series[:n], dtype=float)
        y = np.array(y_series[:n], dtype=float)

        # Remove pairs where either value is NaN
        mask = ~(np.isnan(x) | np.isnan(y))
        x, y = x[mask], y[mask]
        if len(x) < 3:
            return {"error": "Insufficient valid pairs for correlation."}

        # Handle constant input (zero variance) gracefully
        if np.std(x) == 0 or np.std(y) == 0:
            return {
                "pearson_r": None,
                "p_value": None,
                "is_significant": False,
                "strength": "undetermined",
                "interpretation": "Correlation is undefined: one or both series have zero variance (constant values).",
            }

        r, p_value = stats.pearsonr(x, y)
        abs_r = abs(r)
        strength = "strong" if abs_r >= 0.7 else "moderate" if abs_r >= 0.4 else "weak"
        direction = "positive" if r > 0 else "negative"

        return {
            "pearson_r": round(float(r), 4),
            "p_value": round(float(p_value), 4),
            "is_significant": bool(p_value < 0.05),
            "strength": f"{strength} {direction}",
            "interpretation": (
                f"{strength.capitalize()} {direction} correlation (r={r:.3f}, p={p_value:.4f}). "
                f"{'Statistically significant.' if p_value < 0.05 else 'Not statistically significant.'}"
            ),
        }

    @staticmethod
    def rank_groups_by_performance(rows: list, value_key: str = "mean", higher_is_better: bool = True) -> list:
        """
        Rank groups (rows) by a numeric metric.
        Returns the rows with an added 'rank' field, sorted best-first.
        """
        valid = [r for r in rows if isinstance(r.get(value_key), (int, float))]
        ranked = sorted(valid, key=lambda r: r[value_key], reverse=higher_is_better)
        result = []
        for i, row in enumerate(ranked, start=1):
            entry = dict(row)
            entry["rank"] = i
            entry["rank_label"] = f"#{i}"
            result.append(entry)
        return result
