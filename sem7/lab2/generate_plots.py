import os
import time
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict, Counter

from language_detector import LanguageDetector
from main import ROOT_DOCS_FOLDER


def run_evaluation_and_generate_plots():
    """Performs a live evaluation of the language detectors and generates plots."""
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
    except Exception as e:
        print(f"FATAL: Could not scan directory '{ROOT_DOCS_FOLDER}': {e}")
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
        "Neural Net": detector.detect_by_nn,
        "LLM (phi3)": detector.detect_by_llm
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
        report_data.append({"Method": method_name, "Accuracy (%)": accuracy, "Average Time per File (ms)": avg_time_ms})

    df_report = pd.DataFrame(report_data)
    print("\n--- Evaluation Summary ---")
    print(df_report.to_string(index=False))

    # --- Plots will now automatically include the 4th method ---
    plt.figure(figsize=(12, 7))  # Increased width for 4 bars
    acc_plot = sns.barplot(x='Method', y='Accuracy (%)', data=df_report, palette='coolwarm',
                           order=df_report.sort_values('Accuracy (%)', ascending=False)['Method'])
    plt.title('Сравнение точности методов (Accuracy)', fontsize=16)
    plt.xlabel('Метод определения языка', fontsize=12)
    plt.ylabel('Точность, %', fontsize=12)
    plt.ylim(0, 105)
    for p in acc_plot.patches:
        acc_plot.annotate(f'{p.get_height():.1f}%', (p.get_x() + p.get_width() / 2., p.get_height()), ha='center',
                          va='center', xytext=(0, 9), textcoords='offset points')
    plt.tight_layout()
    plt.savefig('plot_accuracy.png')
    print("\nGenerated 'plot_accuracy.png'")

    plt.figure(figsize=(12, 7))  # Increased width for 4 bars
    perf_plot = sns.barplot(x='Method', y='Average Time per File (ms)', data=df_report, palette='viridis',
                            order=df_report.sort_values('Average Time per File (ms)')['Method'])
    plt.yscale('log')
    plt.title('Сравнение быстродействия методов (Среднее время на файл)', fontsize=16)
    plt.xlabel('Метод определения языка', fontsize=12)
    plt.ylabel('Среднее время на 1 файл, мс (Логарифмическая шкала)', fontsize=12)
    for p in perf_plot.patches:
        perf_plot.annotate(f'{p.get_height():.1f} мс', (p.get_x() + p.get_width() / 2., p.get_height()), ha='center',
                           va='bottom', xytext=(0, 5), textcoords='offset points')
    plt.tight_layout()
    plt.savefig('plot_performance.png')
    print("Generated 'plot_performance.png'")

    print("\n--- Evaluation Complete ---")


if __name__ == '__main__':
    run_evaluation_and_generate_plots()