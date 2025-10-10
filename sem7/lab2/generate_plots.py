import os
import time
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

from language_detector import LanguageDetector
from main import ROOT_DOCS_FOLDER


def run_evaluation_and_generate_plots():
    """
    Performs a live evaluation of the language detectors and generates plots.
    1. Scans the corpus_root to build the ground truth based on file prefixes.
    2. Runs each detection method on all files, measuring time and accuracy.
    3. Calculates final metrics.
    4. Generates and saves plots.
    """
    print("--- Starting Live Evaluation and Plot Generation ---")

    ground_truth = {}
    filepaths = []
    try:
        for dirpath, _, filenames in os.walk(ROOT_DOCS_FOLDER):
            for filename in filenames:
                if filename.endswith(".html"):
                    full_path = os.path.join(dirpath, filename)
                    filepaths.append(full_path)
                    if filename.startswith('en_'):
                        ground_truth[full_path] = 'en'
                    elif filename.startswith('es_'):
                        ground_truth[full_path] = 'es'
                    else:
                        print(
                            f"  - Warning: File '{filename}' has no language prefix. It will be ignored in accuracy calculation.")
    except Exception as e:
        print(f"FATAL: Could not scan the directory '{ROOT_DOCS_FOLDER}': {e}")
        return

    if not filepaths:
        print(f"FATAL: No '.html' files found in '{ROOT_DOCS_FOLDER}'. Cannot run evaluation.")
        return

    print(f"\nFound {len(filepaths)} total files.")
    print(f"Ground Truth: {Counter(ground_truth.values())}")

    detector = LanguageDetector()

    methods_to_test = {
        "Alphabet": detector.detect_by_alphabet,
        "N-Gram": detector.detect_by_ngram,
        "Neural Net": detector.detect_by_nn
    }

    results = defaultdict(lambda: {'correct': 0, 'total_time': 0.0})

    for method_name, method_func in methods_to_test.items():
        print(f"\n--- Testing Method: {method_name} ---")

        start_time = time.perf_counter()

        for filepath in filepaths:
            predicted_lang = method_func(filepath)

            if filepath in ground_truth:
                true_lang = ground_truth[filepath]
                if predicted_lang.lower() == true_lang:
                    results[method_name]['correct'] += 1

        end_time = time.perf_counter()
        results[method_name]['total_time'] = end_time - start_time

        print(f"  - Correctly identified: {results[method_name]['correct']} / {len(ground_truth)}")
        print(f"  - Total time for {len(filepaths)} files: {results[method_name]['total_time']:.4f} seconds")

    report_data = []
    for method_name, data in results.items():
        accuracy = (data['correct'] / len(ground_truth)) * 100 if len(ground_truth) > 0 else 0
        avg_time_ms = (data['total_time'] / len(filepaths)) * 1000 if len(filepaths) > 0 else 0

        report_data.append({
            "Method": method_name,
            "Accuracy (%)": accuracy,
            "Average Time per File (ms)": avg_time_ms
        })

    df_report = pd.DataFrame(report_data)
    print("\n--- Evaluation Summary ---")
    print(df_report.to_string(index=False))

    plt.figure(figsize=(10, 6))
    acc_plot = sns.barplot(x='Method', y='Accuracy (%)', data=df_report, palette='coolwarm',
                           order=df_report.sort_values('Accuracy (%)', ascending=False)['Method'])
    plt.title('Comparison of methods accuracy (Accuracy)', fontsize=16)
    plt.xlabel('Language detection method', fontsize=12)
    plt.ylabel('Accuracy, %', fontsize=12)
    plt.ylim(0, 105)
    for p in acc_plot.patches:
        acc_plot.annotate(f'{p.get_height():.1f}%', (p.get_x() + p.get_width() / 2., p.get_height()), ha='center',
                          va='center', xytext=(0, 9), textcoords='offset points')
    plt.tight_layout()
    plt.savefig('plot_accuracy.png')
    print("\nGenerated 'plot_accuracy.png'")

    plt.figure(figsize=(10, 6))
    perf_plot = sns.barplot(x='Method', y='Average Time per File (ms)', data=df_report, palette='viridis',
                            order=df_report.sort_values('Average Time per File (ms)')['Method'])
    plt.yscale('log')
    plt.title('Comparison of the performance of methods (Average time per file)', fontsize=16)
    plt.xlabel('Language detection method', fontsize=12)
    plt.ylabel('Average time per file, ms (Logarithmic scale)', fontsize=12)
    for p in perf_plot.patches:
        perf_plot.annotate(f'{p.get_height():.1f} мс', (p.get_x() + p.get_width() / 2., p.get_height()), ha='center',
                           va='bottom', xytext=(0, 5), textcoords='offset points')
    plt.tight_layout()
    plt.savefig('plot_performance.png')
    print("Generated 'plot_performance.png'")

    print("\n--- Evaluation Complete ---")


if __name__ == '__main__':
    from collections import Counter

    run_evaluation_and_generate_plots()
