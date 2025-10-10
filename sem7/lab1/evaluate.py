from search_engine import VectorSearchEngine
from metrics_calculator import MetricsCalculator
import json

# --- STEP 1: DEFINE YOUR GROUND TRUTH HERE ---
# This is the most important part. You must manually define which files
# are relevant for each of your test queries.
#
# Format:
#   - Key: The search query string.
#   - Value: A list of full paths to the files you consider relevant.
#
# IMPORTANT: Use forward slashes '/' in paths, even on Windows, for consistency.
# Example: "corpus_root/computer1/my_file.txt"

GROUND_TRUTH = {
    "my family": [
        "corpus_root/computer1/file2.txt",
        "corpus_root/computer1/file4.txt",
        "corpus_root/computer3/file2.txt",
        "corpus_root/computer3/file3.txt"
    ],
    "school day": [
        "corpus_root/computer1/file1.txt",
        "corpus_root/computer1/file4.txt",
        "corpus_root/computer1/file5.txt",
        "corpus_root/computer2/file2.txt",
        "corpus_root/computer2/file5.txt",
        "corpus_root/computer3/file3.txt",
        "corpus_root/computer3/file4.txt",
        "corpus_root/computer3/file5.txt"
    ],
    "restaurant": [
        "corpus_root/computer2/file1.txt",
        "corpus_root/computer2/file3.txt"
    ],
    "park": [
        "corpus_root/computer2/file4.txt",
        "corpus_root/computer2/file5.txt",
        "corpus_root/computer3/file2.txt",
        "corpus_root/computer3/file5.txt"
    ],
    "United States": [
        "corpus_root/computer2/file4.txt",
        "corpus_root/computer3/file1.txt",
        "corpus_root/computer3/file2.txt",
        "corpus_root/computer3/file3.txt",
        "corpus_root/computer3/file4.txt"
        "corpus_root/computer3/file5.txt"
    ]
}


def run_evaluation():
    """
    Main function to run the evaluation, print a summary, and save results to a file.
    """
    print("Starting evaluation process...")

    search_engine = VectorSearchEngine()
    search_engine.load_from_cache()

    evaluation_data = {"query_results": []}
    all_query_metrics = []

    for query, relevant_paths in GROUND_TRUTH.items():
        if not relevant_paths:
            print(f"\n--- SKIPPING Query: '{query}' (No ground truth files defined) ---")
            continue

        print(f"\n--- Evaluating Query: '{query}' ---")

        search_results = search_engine.search(query, top_n=100)
        calculator = MetricsCalculator(search_results, relevant_paths)
        metrics = calculator.calculate_all_metrics()

        all_query_metrics.append(metrics)

        # Store results for this query
        evaluation_data["query_results"].append({
            "query": query,
            "metrics": metrics
        })

        # (Printing to console remains the same for immediate feedback)
        print(f"  > Total relevant files (expert): {len(relevant_paths)}")
        print(f"  > Total results found (system):  {len(search_results)}")
        print("-" * 30)
        print(f"  Precision:         {metrics['precision']:.4f}")
        print(f"  Recall:            {metrics['recall']:.4f}")
        print(f"  F1-Score:          {metrics['f1_score']:.4f}")
        print(f"  Average Precision: {metrics['average_precision']:.4f}")

    if all_query_metrics:
        num_queries = len(all_query_metrics)
        map_score = sum(m['average_precision'] for m in all_query_metrics) / num_queries
        evaluation_data['map_score'] = map_score

        print("\n" + "=" * 40)
        print("--- Overall System Performance ---")
        print(f"Mean Average Precision (MAP): {map_score:.4f}")
        print("=" * 40)

        # --- NEW: Save the collected data to a JSON file ---
        output_filename = "evaluation_results.json"
        with open(output_filename, 'w') as f:
            json.dump(evaluation_data, f, indent=4)
        print(f"\nEvaluation results have been saved to '{output_filename}'")
        print("You can now run 'python plot_metrics.py' to generate graphs.")


if __name__ == "__main__":
    run_evaluation()
