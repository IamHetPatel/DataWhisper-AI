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

