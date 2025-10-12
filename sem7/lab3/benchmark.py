import os
import time
import matplotlib.pyplot as plt
from summarizer import DocumentSummarizer, get_text_from_file

# --- Configuration ---
ROOT_DOCS_FOLDER = "benchmark_root"


def run_performance_test():
    """
    Measures the execution time of each summarization method for all documents
    in the corpus and generates a performance chart.
    """
    print("--- Starting Summarization Performance Test ---")

    filepaths = []
    for dirpath, _, filenames in os.walk(ROOT_DOCS_FOLDER):
        for filename in filenames:
            if filename.endswith(".txt"):
                filepaths.append(os.path.join(dirpath, filename))

    if not filepaths:
        print(f"Error: No .txt files found in '{ROOT_DOCS_FOLDER}'. Aborting test.")
        return

    print(f"Found {len(filepaths)} documents to test.")

    print("Initializing DocumentSummarizer and building corpus stats...")
    summarizer = DocumentSummarizer(filepaths)
    print("-" * 20)

    classic_times = []
    ollama_times = []
    file_labels = []

    for filepath in filepaths:
        filename = os.path.basename(filepath)
        file_labels.append(filename)
        print(f"Processing: {filename}")

        try:
            text = get_text_from_file(filepath)

            start_time_classic = time.perf_counter()
            summarizer._get_classic_summary_extractive(text)
            end_time_classic = time.perf_counter()
            duration_classic = end_time_classic - start_time_classic
            classic_times.append(duration_classic)
            print(f"  -> Classic (Extractive) Time: {duration_classic:.4f} seconds")

            start_time_ollama = time.perf_counter()
            summarizer._get_keyword_summary_ollama(text)
            end_time_ollama = time.perf_counter()
            duration_ollama = end_time_ollama - start_time_ollama
            ollama_times.append(duration_ollama)
            print(f"  -> Ollama (Keyword) Time:      {duration_ollama:.4f} seconds")

        except Exception as e:
            print(f"  -> ERROR processing file: {e}")
            classic_times.append(0)
            ollama_times.append(0)

    print("\n--- Test Complete. Generating Chart... ---")

    plot_results(file_labels, classic_times, ollama_times)


def plot_results(labels, classic_times, ollama_times):
    """Generates and saves a bar chart comparing the performance results."""

    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 0.8), 6))

    rects1 = ax.bar([i - width / 2 for i in x], classic_times, width, label='Classic (Extractive)')
    rects2 = ax.bar([i + width / 2 for i in x], ollama_times, width, label='Ollama (Keywords)')

    ax.set_ylabel('Time (seconds)')
    ax.set_title('Summarization Performance Comparison by Document')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.legend()

    ax.bar_label(rects1, padding=3, fmt='%.2f')
    ax.bar_label(rects2, padding=3, fmt='%.2f')

    if max(ollama_times or [0]) > 10 * max(classic_times or [0]):
        ax.set_yscale('log')
        ax.set_ylabel('Time (seconds) - Log Scale')

    fig.tight_layout()

    output_filename = "performance_chart.png"
    plt.savefig(output_filename)
    print(f"Chart saved as '{output_filename}'")

    plt.show()


if __name__ == "__main__":
    run_performance_test()