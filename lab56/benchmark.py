# --- START OF FILE benchmark_dialog_analysis_random.py ---

import time
import spacy
import statistics
import random

# --- Optional NLTK/WordNet ---
WORDNET_AVAILABLE = False
try:
    import nltk
    from nltk.corpus import wordnet as wn
    try:
        wn.synsets('test', pos=wn.NOUN)
        WORDNET_AVAILABLE = True
        print("WordNet data found and accessible.")
    except LookupError:
        print("WordNet data not found. Attempting download...")
        try:
            nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)
            wn.synsets('test', pos=wn.NOUN)
            WORDNET_AVAILABLE = True
            print("WordNet data downloaded.")
        except Exception as e:
            print(f"--- ERROR: Failed to download WordNet data: {e} ---")
    except Exception as e:
        print(f"Error accessing WordNet: {e}")
except ImportError:
    print("NLTK not installed. WordNet features disabled.")

# --- Optional Plotting ---
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    MATPLOTLIB_AVAILABLE = True
    print("Matplotlib found, plotting enabled.")
except ImportError:
    print("Matplotlib not found. Plotting disabled. Install with: pip install matplotlib")

# --- Utils (placeholders if utils.py is missing) ---
try:
    from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token
except ImportError:
    print("Warning: utils.py not found. Using basic placeholder functions.")
    POS_TAG_TRANSLATIONS = {}
    def beautiful_morph(d): return str(d) if d else "None"
    def clean_token(t): return t.strip()

# --- Benchmark Configuration ---
NUM_TEXTS_TO_BENCHMARK = 300              # How many random texts to generate and process
NUM_RUNS = 5                             # Number of benchmark repetitions for averaging
SPACY_MODEL_NAME = 'en_core_web_sm'      # spaCy model to use
MIN_WORDS_PER_SENTENCE = 10
MAX_WORDS_PER_SENTENCE = 25
MIN_SENTENCES_PER_TEXT = 5
MAX_SENTENCES_PER_TEXT = 10
ENABLE_WORDNET_BENCHMARK = WORDNET_AVAILABLE # Only benchmark WordNet if available
MAX_TEXTS_ON_BAR_CHART = 30              # Limit bars on the plot for readability
# ---

# --- Vocabulary for Random Text Generation ---
# (Simple list, could be expanded or loaded from a file/NLTK)
VOCABULARY = [
    'movie', 'film', 'cinema', 'actor', 'actress', 'director', 'plot', 'story',
    'scene', 'character', 'dialogue', 'script', 'genre', 'action', 'comedy',
    'drama', 'thriller', 'horror', 'sci-fi', 'fantasy', 'animation', 'documentary',
    'review', 'rating', 'recommend', 'suggest', 'watch', 'see', 'like', 'enjoy',
    'good', 'bad', 'great', 'terrible', 'interesting', 'boring', 'oscar',
    'award', 'festival', 'release', 'sequel', 'prequel', 'effects', 'music',
    'cinematography', 'editing', 'production', 'studio', 'box', 'office', 'hit',
    'the', 'a', 'is', 'was', 'were', 'in', 'on', 'at', 'of', 'with', 'about',
    'and', 'or', 'but', 'it', 'he', 'she', 'they', 'we', 'you', 'i', 'my', 'your',
    'really', 'very', 'quite', 'some', 'any', 'what', 'who', 'when', 'where', 'why', 'how',
    'think', 'know', 'believe', 'remember', 'forget', 'love', 'hate', 'prefer',
    'show', 'tell', 'ask', 'explain', 'describe', 'talk', 'discuss', 'go', 'come',
    'make', 'do', 'have', 'be', 'get', 'set', 'new', 'old', 'classic', 'modern',
    'independent', 'blockbuster', 'popular', 'famous', 'unknown'
]

# --- Global spaCy Model ---
NLP = None

def load_spacy_model():
    """Loads the global spaCy model."""
    global NLP
    if NLP is None:
        print(f"Loading spaCy model '{SPACY_MODEL_NAME}'...")
        try:
            NLP = spacy.load(SPACY_MODEL_NAME)
            print("spaCy model loaded successfully.")
            return True
        except OSError:
            print(f"--- ERROR: spaCy model '{SPACY_MODEL_NAME}' not found! ---")
            print(f"Download it: python -m spacy download {SPACY_MODEL_NAME}")
            return False
        except Exception as e:
            print(f"--- ERROR: Could not load spaCy model: {e} ---")
            return False
    return True

def generate_random_text(min_sentences, max_sentences, min_words, max_words):
    """Generates a random text snippet."""
    num_sentences = random.randint(min_sentences, max_sentences)
    sentences = []
    for _ in range(num_sentences):
        num_words = random.randint(min_words, max_words)
        # Sample words with replacement
        sentence_words = random.choices(VOCABULARY, k=num_words)
        # Simple sentence structure: Capitalize first word, add period.
        sentence = " ".join(sentence_words).capitalize() + random.choice(['.', '?', '!'])
        sentences.append(sentence)
    return " ".join(sentences)

# --- WordNet Helper Functions ---
def map_spacy_pos_to_wordnet(spacy_pos_tag):
    if spacy_pos_tag in ['NOUN', 'PROPN']: return wn.NOUN
    if spacy_pos_tag == 'VERB': return wn.VERB
    if spacy_pos_tag == 'ADJ': return wn.ADJ
    if spacy_pos_tag == 'ADV': return wn.ADV
    return None

def get_wordnet_info(lemma, spacy_pos_tag):
    if not WORDNET_AVAILABLE:
        return {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}
    wn_pos = map_spacy_pos_to_wordnet(spacy_pos_tag)
    results = {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}
    if not wn_pos: return results
    try:
        synsets = wn.synsets(lemma, pos=wn_pos)
        if not synsets: return results
        first_synset = synsets[0]
        results["definition"] = first_synset.definition() or "N/A"
        synonyms = set(); limit = 3
        for lem in first_synset.lemmas():
            syn_name = lem.name().replace('_', ' ')
            if syn_name.lower() != lemma.lower(): synonyms.add(syn_name)
            if len(synonyms) >= limit: break
        results["synonyms"] = ", ".join(sorted(list(synonyms))) if synonyms else "N/A"
        antonyms = set(); limit = 3
        first_lemma_in_synset = first_synset.lemmas()[0] if first_synset.lemmas() else None
        if first_lemma_in_synset:
            for ant in first_lemma_in_synset.antonyms():
                antonyms.add(ant.name().replace('_', ' '))
                if len(antonyms) >= limit: break
        results["antonyms"] = ", ".join(sorted(list(antonyms))) if antonyms else "N/A"
    except Exception as e:
         print(f"\nWarning: WordNet lookup error for '{lemma}' ({spacy_pos_tag}): {e}")
    return results

# --- Benchmark Execution Function ---
def run_analysis_benchmark(texts_data):
    """Runs the analysis simulation and returns timing results."""
    global NLP
    if not NLP: return [], 0

    results = []
    total_tokens_processed = 0
    wordnet_lookup_errors = 0
    print(f"  Processing {len(texts_data)} texts...")
    progress_interval = max(1, len(texts_data) // 10)

    for i, text_info in enumerate(texts_data):
        text_id = text_info["id"] # Use generated ID
        text_content = text_info["content"]

        if (i + 1) % progress_interval == 0 or i == len(texts_data) - 1:
            print(f"    Processed {i+1}/{len(texts_data)}...", end='\r')

        t_start_spacy = time.perf_counter()
        try:
            doc = NLP(text_content)
        except Exception as e:
            print(f"\n--- ERROR: spaCy failed on text ID {text_id}: {e} ---")
            continue
        t_end_spacy = time.perf_counter()
        spacy_time = t_end_spacy - t_start_spacy
        token_count = len(doc)
        total_tokens_processed += token_count

        t_start_features = time.perf_counter()
        wn_errors_in_text = 0
        for token in doc:
            _ = token.text.lower()
            _ = token.lemma_
            _ = token.pos_
            _ = token.dep_
            _ = beautiful_morph(token.morph.to_dict())

            if ENABLE_WORDNET_BENCHMARK:
                if token.pos_ in ['NOUN', 'VERB', 'ADJ', 'ADV']:
                    try: _ = get_wordnet_info(token.lemma_, token.pos_)
                    except Exception: wn_errors_in_text += 1

        t_end_features = time.perf_counter()
        feature_time = t_end_features - t_start_features
        if wn_errors_in_text > 0: wordnet_lookup_errors += 1

        results.append({
            "id": text_id,
            "length": len(text_content),
            "tokens": token_count,
            "spacy_time": spacy_time,
            "feature_time": feature_time,
            "total_time": spacy_time + feature_time
        })

    print(f"\n  Processing complete. Texts with WordNet errors: {wordnet_lookup_errors}")
    return results, total_tokens_processed

# --- Plotting Functions (Keep as they are, but update labels if needed) ---
def plot_time_per_text(run_results, max_texts=MAX_TEXTS_ON_BAR_CHART):
    if not MATPLOTLIB_AVAILABLE or not run_results: return
    # Sort by total time descending to show slowest texts
    results_to_plot = sorted(run_results, key=lambda x: x['total_time'], reverse=True)[:max_texts]
    num_bars = len(results_to_plot)
    if num_bars == 0: return

    labels = [f"Text {res['id']}" for res in results_to_plot] # Use generated ID
    spacy_times = [res['spacy_time'] for res in results_to_plot]
    feature_times = [res['feature_time'] for res in results_to_plot]
    x = range(num_bars)

    fig, ax = plt.subplots(figsize=(max(10, num_bars * 0.4), 7))
    ax.bar(x, spacy_times, label=f'spaCy Processing ({SPACY_MODEL_NAME})')
    ax.bar(x, feature_times, bottom=spacy_times, label=f'Feature Extraction{" + WordNet" if ENABLE_WORDNET_BENCHMARK else ""}')
    ax.set_ylabel('Time (seconds)')
    ax.set_title(f'Processing Time per Generated Text (Top {num_bars} Slowest)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=90, ha='center', fontsize=8)
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.4f'))
    plt.tight_layout()
    print("Plotting: Time per Text")

def plot_time_distribution(all_times_dict):
    if not MATPLOTLIB_AVAILABLE or not all_times_dict: return
    labels = list(all_times_dict.keys())
    data_to_plot = [d for d in all_times_dict.values() if d]
    valid_labels = [lbl for lbl, d in zip(labels, all_times_dict.values()) if d]
    if not data_to_plot: print("No data for time distribution plot."); return

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.boxplot(data_to_plot, labels=valid_labels, showfliers=True)
    ax.set_ylabel('Time (seconds)')
    ax.set_title('Distribution of Processing Times (Across All Texts & Runs)')
    ax.yaxis.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.5)
    plt.tight_layout()
    print("Plotting: Time Distribution")

def plot_time_vs_tokens(run_results):
    if not MATPLOTLIB_AVAILABLE or not run_results: return
    tokens = [res['tokens'] for res in run_results]
    total_times = [res['total_time'] for res in run_results]
    if not tokens or not total_times: print("No data for time vs tokens plot."); return

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(tokens, total_times, alpha=0.5, edgecolors='k', s=30)
    ax.set_xlabel('Number of Tokens')
    ax.set_ylabel('Total Processing Time (seconds)')
    ax.set_title('Processing Time vs. Number of Tokens per Text (One Run)')
    ax.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.5)
    try: # Optional trend line
        import numpy as np
        if len(tokens) > 1:
            coeffs = np.polyfit(tokens, total_times, 1)
            poly1d_fn = np.poly1d(coeffs)
            tokens_sorted = sorted(list(set(tokens))) # Use unique sorted tokens for line
            ax.plot(tokens_sorted, poly1d_fn(tokens_sorted), '--r', label=f'Trend (y={coeffs[0]:.2e}x+{coeffs[1]:.3f})')
            ax.legend()
    except ImportError: pass
    except Exception as e: print(f"Could not plot trend line: {e}")
    plt.tight_layout()
    print("Plotting: Time vs Tokens")

# --- Main Execution Block ---
if __name__ == "__main__":
    print("--- Benchmark for Dialog NLP Analysis Simulation (Random Text) ---")

    # 1. Load spaCy Model
    if not load_spacy_model():
        exit()

    # 2. Generate Sample Inputs
    print(f"\nGenerating {NUM_TEXTS_TO_BENCHMARK} random text snippets...")
    sample_texts = []
    for i in range(NUM_TEXTS_TO_BENCHMARK):
        random_text = generate_random_text(
            MIN_SENTENCES_PER_TEXT, MAX_SENTENCES_PER_TEXT,
            MIN_WORDS_PER_SENTENCE, MAX_WORDS_PER_SENTENCE
        )
        sample_texts.append({"id": i, "content": random_text}) # Assign simple ID
    print(f"Generated {len(sample_texts)} texts.")
    if not sample_texts:
        print("--- ERROR: Failed to generate any sample texts. ---")
        exit()

    # 3. Run Benchmark Multiple Times
    num_texts_in_run = len(sample_texts)
    all_run_results_list = []
    all_run_token_counts = []
    print(f"\nRunning benchmark: {NUM_RUNS} runs, {num_texts_in_run} texts per run...")
    total_benchmark_start_time = time.perf_counter()

    for run_num in range(NUM_RUNS):
        print(f"--- Run {run_num + 1}/{NUM_RUNS} ---")
        # Optional: Generate new random texts for each run?
        # If needed, move text generation inside this loop
        run_results, run_tokens = run_analysis_benchmark(sample_texts)
        if not run_results:
            print(f"!!! ERROR: Run {run_num + 1} failed. Stopping. !!!")
            exit()
        all_run_results_list.append(run_results)
        all_run_token_counts.append(run_tokens)

    total_benchmark_time = time.perf_counter() - total_benchmark_start_time
    print(f"\n--- Benchmark Complete (Total time: {total_benchmark_time:.3f}s) ---")

    # 4. Aggregate and Calculate Statistics
    agg_spacy_times = []
    agg_feature_times = []
    agg_total_times = []
    total_docs_processed_all_runs = 0
    total_tokens_processed_all_runs = sum(all_run_token_counts)

    for run_res in all_run_results_list:
        total_docs_processed_all_runs += len(run_res)
        agg_spacy_times.extend([r['spacy_time'] for r in run_res])
        agg_feature_times.extend([r['feature_time'] for r in run_res])
        agg_total_times.extend([r['total_time'] for r in run_res])

    if not agg_total_times:
        print("No timing results collected.")
        exit()

    # Calculate averages and stdevs
    avg_spacy = statistics.mean(agg_spacy_times)
    avg_feature = statistics.mean(agg_feature_times)
    avg_total = statistics.mean(agg_total_times)
    stdev_spacy = statistics.stdev(agg_spacy_times) if len(agg_spacy_times) > 1 else 0
    stdev_feature = statistics.stdev(agg_feature_times) if len(agg_feature_times) > 1 else 0
    stdev_total = statistics.stdev(agg_total_times) if len(agg_total_times) > 1 else 0
    tokens_per_sec = total_tokens_processed_all_runs / total_benchmark_time if total_benchmark_time > 0 else 0
    pure_spacy_time_total = sum(agg_spacy_times)
    spacy_tokens_per_sec = total_tokens_processed_all_runs / pure_spacy_time_total if pure_spacy_time_total > 0 else 0

    # 5. Print Summary Statistics
    print("\n--- Overall Benchmark Statistics ---")
    print(f"spaCy Model:             {SPACY_MODEL_NAME}")
    print(f"WordNet Lookups:         {'Enabled' if ENABLE_WORDNET_BENCHMARK else 'Disabled'}")
    print(f"Number of Runs:          {NUM_RUNS}")
    print(f"Generated Texts per Run: {num_texts_in_run}")
    print(f"Total Texts Processed:   {total_docs_processed_all_runs}")
    print(f"Total Tokens Processed:  {total_tokens_processed_all_runs}")
    print(f"Total Benchmark Time:    {total_benchmark_time:.3f} s")
    print("-" * 35)
    print("Average Time per Text (Across all runs):")
    print(f"  - spaCy Processing:    {avg_spacy:.6f} s (± {stdev_spacy:.6f})")
    print(f"  - Feature Extraction:  {avg_feature:.6f} s (± {stdev_feature:.6f})")
    print(f"  - Total per Text:      {avg_total:.6f} s (± {stdev_total:.6f})")
    print("-" * 35)
    print("Processing Speed:")
    print(f"  - Overall Speed:       {tokens_per_sec:.2f} tokens/sec")
    print(f"  - spaCy Speed:         {spacy_tokens_per_sec:.2f} tokens/sec")
    print("-" * 35)

    # 6. Generate Plots (if enabled)
    if MATPLOTLIB_AVAILABLE and all_run_results_list:
        print("\nGenerating plots (using results from the first run)...")
        try:
            first_run_results = all_run_results_list[0]
            plot_time_per_text(first_run_results)
            times_for_dist_plot = {
                f'spaCy ({SPACY_MODEL_NAME})': agg_spacy_times,
                f'Features{" + WN" if ENABLE_WORDNET_BENCHMARK else ""}': agg_feature_times,
                'Total Time': agg_total_times }
            plot_time_distribution(times_for_dist_plot)
            plot_time_vs_tokens(first_run_results)
            print("Displaying plots... Close plot windows to exit.")
            plt.show()
        except Exception as e:
            print(f"\n--- ERROR generating plots: {e} ---")

    print("\nBenchmark finished.")

# --- END OF FILE benchmark_dialog_analysis_random.py ---