import time
import os
import spacy
import statistics
import random
from bs4 import BeautifulSoup

# Попытка импорта matplotlib и numpy
try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("\n--- Warning: matplotlib library not found. ---")
    print("Plots will not be generated.")
    print("Install it: pip install matplotlib")
    print("-" * 55 + "\n")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("\n--- Warning: numpy library not found. ---")
    print("Trendline on scatter plot will not be generated.")
    print("Install it: pip install numpy")
    print("-" * 55 + "\n")

# Импорт утилит (предполагается, что utils.py существует)
try:
    from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token
except ImportError:
    print("Error: utils.py not found. Using basic placeholders.")
    POS_TAG_TRANSLATIONS = {}
    def beautiful_morph(d): return str(d) if d else "None"
    def clean_token(t): return t.strip()

# --- Benchmark Configuration ---
HTML_FILES_DIR = "benchmark_html_files"  # Directory containing test HTML files
NUM_FILES_TO_BENCHMARK = 0              # Number of HTML files to test (0 = all in dir)
NUM_RUNS = 2                            # Number of benchmark runs for averaging
SPACY_MODEL_NAME = 'en_core_web_sm'
MAX_FILES_ON_BAR_CHART = 25             # Limit items on the bar chart for readability
# ---

def load_spacy_model():
    """Loads the spaCy model."""
    print(f"Loading spaCy model '{SPACY_MODEL_NAME}'...")
    start_load_time = time.perf_counter()
    try:
        nlp = spacy.load(SPACY_MODEL_NAME)
        load_duration = time.perf_counter() - start_load_time
        print(f"Model loaded in {load_duration:.4f} seconds.")
        return nlp
    except OSError:
        print(f"\n!!! ERROR: spaCy model '{SPACY_MODEL_NAME}' not found. !!!")
        print(f"Download it: python -m spacy download {SPACY_MODEL_NAME}")
        return None
    except Exception as e:
        print(f"!!! Error loading spaCy model: {e}")
        return None

def find_html_files(directory, num_files):
    """Finds HTML files in the specified directory."""
    print(f"Scanning directory '{directory}' for HTML files...")
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' not found.")
        return []
    try:
        all_files = [os.path.join(directory, f) for f in os.listdir(directory)
                     if f.lower().endswith(('.html', '.htm')) and os.path.isfile(os.path.join(directory, f))]
    except OSError as e:
        print(f"Error reading directory '{directory}': {e}")
        return []

    if not all_files:
        print(f"Error: No HTML files found in '{directory}'.")
        return []

    if num_files > 0 and num_files < len(all_files):
        print(f"Selecting {num_files} random HTML files.")
        return random.sample(all_files, num_files)
    else:
        print(f"Using all {len(all_files)} found HTML files.")
        return all_files

def extract_text_from_html(filepath):
    """Loads HTML and extracts text using BeautifulSoup."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        return text
    except FileNotFoundError:
        print(f"\nError: File not found during extraction: {filepath}")
        return None
    except Exception as e:
        print(f"\nError parsing HTML file {os.path.basename(filepath)}: {e}")
        return None

def benchmark_single_file(nlp, filepath):
    """Runs the benchmark steps for a single file."""
    filename = os.path.basename(filepath)
    results = {"filename": filename, "error": None}

    # 1. Time HTML Loading and Text Extraction
    start_time = time.perf_counter()
    text_content = extract_text_from_html(filepath)
    html_duration = time.perf_counter() - start_time
    results["html_time"] = html_duration
    if text_content is None:
        results["error"] = "HTML Parsing Failed"
        return results
    results["text_length"] = len(text_content)
    if not text_content.strip(): # Handle empty extracted text
         results["error"] = "Empty Text Extracted"
         results["tokens"] = 0
         results["spacy_time"] = 0
         results["feature_time"] = 0
         results["total_time"] = html_duration
         print(f"\nWarning: Empty text extracted from {filename}.")
         return results


    # 2. Time spaCy Processing (nlp(text))
    start_time = time.perf_counter()
    try:
        doc = nlp(text_content)
    except Exception as e:
        print(f"\nError processing text from {filename} with spaCy: {e}")
        results["error"] = "spaCy Processing Failed"
        return results
    spacy_duration = time.perf_counter() - start_time
    results["spacy_time"] = spacy_duration
    results["tokens"] = len(doc)

    # 3. Time Feature Extraction Simulation
    start_time = time.perf_counter()
    try:
        # Simulate accessing common attributes like in _populate_analysis_table
        # We don't store the results, just access them to measure time
        for token in doc:
            if not token.is_space:
                _ = token.lemma_
                _ = token.pos_
                _ = token.dep_
                _ = token.morph # Accessing morph is slightly more complex
                # _ = beautiful_morph(token.morph.to_dict()) # Uncomment if you use this heavily
    except Exception as e:
        print(f"\nError during feature extraction simulation for {filename}: {e}")
        # Log error but continue timing
        results["error"] = "Feature Extraction Simulation Failed" # Mark potential issue
    feature_duration = time.perf_counter() - start_time
    results["feature_time"] = feature_duration

    results["total_time"] = html_duration + spacy_duration + feature_duration
    return results

# --- Plotting Functions ---

def plot_time_per_file(run_results, max_files=MAX_FILES_ON_BAR_CHART):
    """Plots stacked bar chart of processing time per file."""
    if not MATPLOTLIB_AVAILABLE or not run_results: return

    # Sort by total time descending and limit number of files shown
    sorted_results = sorted([r for r in run_results if r.get("error") is None],
                            key=lambda x: x.get('total_time', 0), reverse=True)
    results_to_plot = sorted_results[:max_files]
    num_bars = len(results_to_plot)
    if num_bars == 0: print("No successful results to plot for time per file."); return

    labels = [res['filename'] for res in results_to_plot]
    html_times = [res.get('html_time', 0) for res in results_to_plot]
    spacy_times = [res.get('spacy_time', 0) for res in results_to_plot]
    feature_times = [res.get('feature_time', 0) for res in results_to_plot]

    x = range(num_bars)
    fig, ax = plt.subplots(figsize=(max(10, num_bars * 0.6), 7)) # Adjust size

    # Stacked bars
    ax.bar(x, html_times, label='HTML Load/Parse')
    ax.bar(x, spacy_times, bottom=html_times, label='spaCy Processing')
    ax.bar(x, feature_times, bottom=[h + s for h, s in zip(html_times, spacy_times)], label='Feature Extraction')

    ax.set_ylabel('Time (seconds)')
    ax.set_title(f'Processing Time per File (Top {num_bars} Slowest)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=80, ha='right', fontsize=9)
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.3f'))
    plt.tight_layout()

def plot_time_distribution(all_times_dict):
    """Plots box plot for the distribution of timings."""
    if not MATPLOTLIB_AVAILABLE or not all_times_dict: return

    # Filter out empty lists
    valid_data = {k: v for k, v in all_times_dict.items() if v}
    if not valid_data: print("No valid data for time distribution plot."); return

    labels = list(valid_data.keys())
    data_to_plot = list(valid_data.values())

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.boxplot(data_to_plot, labels=labels, showfliers=True) # showfliers=False to hide outliers
    ax.set_ylabel('Time (seconds)')
    ax.set_title('Distribution of Processing Times Across All Files & Runs')
    ax.yaxis.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.7)
    plt.tight_layout()

def plot_time_vs_tokens(run_results):
    """Plots scatter plot of total time vs. number of tokens."""
    if not MATPLOTLIB_AVAILABLE or not run_results: return

    # Filter out results with errors or zero tokens
    valid_results = [r for r in run_results if r.get("error") is None and r.get("tokens", 0) > 0]
    if not valid_results: print("No valid data for time vs tokens plot."); return

    tokens = [res['tokens'] for res in valid_results]
    total_times = [res['total_time'] for res in valid_results]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(tokens, total_times, alpha=0.6, edgecolors='w', s=40)
    ax.set_xlabel('Number of Tokens')
    ax.set_ylabel('Total Processing Time (seconds)')
    ax.set_title('Total Processing Time vs. Number of Tokens per File')
    ax.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.7)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.3f'))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: format(int(x), ','))) # Format x-axis ticks

    # Optional: Add trendline if numpy is available
    if NUMPY_AVAILABLE and len(tokens) > 1:
        try:
            coeffs = np.polyfit(tokens, total_times, 1)
            poly1d_fn = np.poly1d(coeffs)
            tokens_sorted = sorted(tokens)
            ax.plot(tokens_sorted, poly1d_fn(tokens_sorted), '--r', label=f'Trend (y={coeffs[0]:.2e}x+{coeffs[1]:.3f})')
            ax.legend()
        except Exception as e:
            print(f"Could not plot trendline: {e}")

    plt.tight_layout()

# --- Main Execution ---
if __name__ == "__main__":
    print("--- SessionApp Benchmark ---")

    # 1. Load spaCy Model
    nlp = load_spacy_model()
    if nlp is None: exit()

    # 2. Find HTML Files
    html_files = find_html_files(HTML_FILES_DIR, NUM_FILES_TO_BENCHMARK)
    if not html_files: exit()

    num_files = len(html_files)
    all_run_results_list = [] # Store results from each run

    # 3. Run Benchmark Multiple Times
    print(f"\nStarting benchmark ({NUM_RUNS} runs, {num_files} files per run)...")
    total_benchmark_start_time = time.perf_counter()

    for run_num in range(NUM_RUNS):
        print(f"--- Run {run_num + 1}/{NUM_RUNS} ---")
        run_results = []
        run_start_time = time.perf_counter()
        processed_count = 0
        for i, filepath in enumerate(html_files):
             if (i + 1) % 5 == 0 or i == num_files - 1: # Update progress occasionally
                  print(f"  Processing file {i+1}/{num_files}...", end='\r')
             result = benchmark_single_file(nlp, filepath)
             run_results.append(result)
             if result.get("error") is None: processed_count+=1

        run_duration = time.perf_counter() - run_start_time
        print(f"\n  Run {run_num + 1} finished in {run_duration:.3f} seconds. ({processed_count}/{num_files} files processed successfully)")
        all_run_results_list.append(run_results)

    total_benchmark_duration = time.perf_counter() - total_benchmark_start_time
    print(f"\n--- Benchmark Finished (Total time: {total_benchmark_duration:.3f} seconds) ---")

    # 4. Aggregate Results Across Runs
    aggregated_results = {
        "html_time": [], "spacy_time": [], "feature_time": [], "total_time": [],
        "tokens": [], "text_length": []
    }
    total_docs_processed = 0
    total_tokens_processed = 0
    failed_files = set()

    for run_res in all_run_results_list:
        for res in run_res:
            if res.get("error") is None:
                total_docs_processed += 1
                total_tokens_processed += res.get('tokens', 0)
                for key in aggregated_results.keys():
                    if key in res:
                        aggregated_results[key].append(res[key])
            else:
                 failed_files.add(res["filename"])

    # 5. Print Statistics
    print("\n--- Aggregate Statistics ---")
    print(f"spaCy Model:             {SPACY_MODEL_NAME}")
    print(f"Number of Runs:          {NUM_RUNS}")
    print(f"Files Per Run:           {num_files}")
    if failed_files:
        print(f"Files Failed Processing: {len(failed_files)} ({', '.join(list(failed_files)[:5])}{'...' if len(failed_files)>5 else ''})")
    print(f"Total Successful Docs:   {total_docs_processed}")
    print(f"Total Tokens Processed:  {total_tokens_processed:,}") # Formatted number
    print(f"Total Benchmark Duration:{total_benchmark_duration:.3f} sec")

    if total_docs_processed > 0:
        avg_html_time = statistics.mean(aggregated_results["html_time"])
        avg_spacy_time = statistics.mean(aggregated_results["spacy_time"])
        avg_feature_time = statistics.mean(aggregated_results["feature_time"])
        avg_total_time = statistics.mean(aggregated_results["total_time"])
        avg_tokens = statistics.mean(aggregated_results["tokens"])
        avg_length = statistics.mean(aggregated_results["text_length"])

        stdev_html = statistics.stdev(aggregated_results["html_time"]) if len(aggregated_results["html_time"]) > 1 else 0
        stdev_spacy = statistics.stdev(aggregated_results["spacy_time"]) if len(aggregated_results["spacy_time"]) > 1 else 0
        stdev_feature = statistics.stdev(aggregated_results["feature_time"]) if len(aggregated_results["feature_time"]) > 1 else 0
        stdev_total = statistics.stdev(aggregated_results["total_time"]) if len(aggregated_results["total_time"]) > 1 else 0

        print("-" * 30)
        print("Average Time Per File:")
        print(f"  - HTML Load/Parse:    {avg_html_time:.6f} sec (± {stdev_html:.6f})")
        print(f"  - spaCy Processing:   {avg_spacy_time:.6f} sec (± {stdev_spacy:.6f})")
        print(f"  - Feature Extraction: {avg_feature_time:.6f} sec (± {stdev_feature:.6f})")
        print(f"  - Total Time:         {avg_total_time:.6f} sec (± {stdev_total:.6f})")
        print("-" * 30)
        print(f"Average Tokens Per File: {avg_tokens:,.1f}")
        print(f"Average Text Length:     {avg_length:,.0f} chars")

        if total_tokens_processed > 0 and total_benchmark_duration > 0:
            overall_tokens_per_sec = total_tokens_processed / total_benchmark_duration
            print(f"Overall Speed:           {overall_tokens_per_sec:,.1f} tokens/sec")
            total_spacy_aggregate_time = sum(aggregated_results["spacy_time"])
            if total_spacy_aggregate_time > 0:
                 spacy_tokens_per_sec = total_tokens_processed / total_spacy_aggregate_time
                 print(f"spaCy Processing Speed:  {spacy_tokens_per_sec:,.1f} tokens/sec")
        else:
             print("Could not calculate processing speed.")
    else:
         print("\nNo files processed successfully, cannot calculate statistics.")

    # 6. Generate Plots (if matplotlib is available)
    if MATPLOTLIB_AVAILABLE and total_docs_processed > 0:
        print("\nGenerating plots...")
        try:
            # Use results from the first run for per-file plots
            first_run_successful_results = [r for r in all_run_results_list[0] if r.get("error") is None]

            plot_time_per_file(first_run_successful_results)

            plot_time_distribution({
                'HTML Load': aggregated_results["html_time"],
                'spaCy Process': aggregated_results["spacy_time"],
                'Feature Extract': aggregated_results["feature_time"],
                'Total Time': aggregated_results["total_time"]
                })

            plot_time_vs_tokens(first_run_successful_results)

            print("Displaying plots (may appear behind other windows)...")
            plt.show()
        except Exception as e:
            print(f"\n--- Error generating plots: {e} ---")
    elif not MATPLOTLIB_AVAILABLE:
        print("\nSkipping plot generation (matplotlib not found).")
    else:
        print("\nSkipping plot generation (no successful results).")
