# metrics_calculator.py

class MetricsCalculator:
    """
    Calculates various search evaluation metrics for a single query.
    Based on the ROMIP'2004 methodology.
    """

    def __init__(self, search_results, ground_truth_relevant_paths):
        self.ranked_result_paths = [res['path'] for res in search_results]
        self.ground_truth_paths = set(ground_truth_relevant_paths)

        self.tp_set = set(self.ranked_result_paths) & self.ground_truth_paths
        self.tp = len(self.tp_set)
        self.fp = len(self.ranked_result_paths) - self.tp
        self.fn = len(self.ground_truth_paths) - self.tp

    def calculate_precision(self):
        """Calculates Precision = TP / (TP + FP)."""
        denominator = self.tp + self.fp
        return self.tp / denominator if denominator > 0 else 0.0

    def calculate_recall(self):
        """Calculates Recall = TP / (TP + FN)."""
        denominator = self.tp + self.fn
        return self.tp / denominator if denominator > 0 else 0.0

    def calculate_f1_score(self):
        """Calculates F1-Score."""
        precision = self.calculate_precision()
        recall = self.calculate_recall()
        denominator = precision + recall
        return 2 * (precision * recall) / denominator if denominator > 0 else 0.0

    def calculate_precision_at_k(self, k):
        """Calculates Precision@k."""
        top_k_results = self.ranked_result_paths[:k]
        relevant_in_top_k = len(set(top_k_results) & self.ground_truth_paths)
        return relevant_in_top_k / k if k > 0 else 0.0

    def calculate_r_precision(self):
        """Calculates R-Precision."""
        r = len(self.ground_truth_paths)
        return self.calculate_precision_at_k(r) if r > 0 else 0.0

    def calculate_average_precision(self):
        """Calculates Average Precision (AvgPrec)."""
        total_relevant_docs = len(self.ground_truth_paths)
        if total_relevant_docs == 0: return 0.0

        running_sum = 0.0
        hits = 0
        for i, doc_path in enumerate(self.ranked_result_paths):
            rank = i + 1
            if doc_path in self.ground_truth_paths:
                hits += 1
                precision_at_this_rank = hits / rank
                running_sum += precision_at_this_rank

        return running_sum / total_relevant_docs

    # --- NEW: Function to calculate the 11-point interpolated precision ---
    def calculate_interpolated_precision_recall_points(self):
        """
        Calculates the 11-point interpolated precision as per TREC methodology.
        This is used for the Precision-Recall curve.
        """
        total_relevant_docs = len(self.ground_truth_paths)
        if total_relevant_docs == 0:
            return [0.0] * 11

        # 1. Calculate precision/recall at each point a relevant document is found
        recall_precision_pairs = []
        hits = 0
        for i, doc_path in enumerate(self.ranked_result_paths):
            rank = i + 1
            if doc_path in self.ground_truth_paths:
                hits += 1
                recall_val = hits / total_relevant_docs
                precision_val = hits / rank
                recall_precision_pairs.append((recall_val, precision_val))

        # 2. Interpolate precision for the 11 standard recall levels (0.0 to 1.0)
        interpolated_precisions = []
        recall_levels = [i / 10.0 for i in range(11)]

        for r_level in recall_levels:
            # Find max precision for any recall level >= r_level
            precisions_at_or_after_recall = [p for r, p in recall_precision_pairs if r >= r_level]
            max_precision = max(precisions_at_or_after_recall) if precisions_at_or_after_recall else 0.0
            interpolated_precisions.append(max_precision)

        return interpolated_precisions

    def calculate_all_metrics(self):
        """Runs all calculations and returns them in a dictionary."""
        return {
            'precision': self.calculate_precision(),
            'recall': self.calculate_recall(),
            'f1_score': self.calculate_f1_score(),
            'precision_at_5': self.calculate_precision_at_k(5),
            'precision_at_10': self.calculate_precision_at_k(10),
            'r_precision': self.calculate_r_precision(),
            'average_precision': self.calculate_average_precision(),
            'interpolated_precision_points': self.calculate_interpolated_precision_recall_points()
        }