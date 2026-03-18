import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from services.stats_engine import StatsEngine

def main():
    engine = StatsEngine()
    
    data_points = [10.5, 11.2, 10.8, 11.0, 10.7, 10.9, 11.1, 10.6, 25.0]  # Array with one clear anomaly (25.0)
    
    print("--- Testing Drift ---")
    print(engine.calculate_drift(data_points))
    
    print("\n--- Testing Anomalies ---")
    print(engine.find_anomalies(data_points, threshold=2.0))
    
    print("\n--- Testing Comparison ---")
    group_a = [50.1, 51.2, 50.8, 49.9, 50.5]
    group_b = [45.1, 46.2, 45.8, 44.9, 45.5] # Clear difference
    print(engine.compare_means(group_a, group_b))

if __name__ == "__main__":
    main()
