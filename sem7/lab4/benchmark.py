import requests
import time
import matplotlib.pyplot as plt
import seaborn as sns
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
import threading
import sys

# --- Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODELS_TO_TEST = ['llama3.1:8b', 'llama3.2:1b']

# --- Test Data ---
# Domain: Computer Science (article excerpt)
SOURCE_TEXT_EN = (
    "Machine learning is a method of data analysis that automates analytical model building. "
    "It is a branch of artificial intelligence based on the idea that systems can learn from data, "
    "identify patterns and make decisions with minimal human intervention. "
    "The process of learning begins with observations or data, such as examples, direct experience, or instruction, "
    "in order to look for patterns in data and make better decisions in the future based on the examples that we provide."
)

# Reference translation (human-made or from a high-quality system for comparison)
# This is the only part that remains in Russian, as it's part of the data.
REFERENCE_TRANSLATION_RU = (
    "Машинное обучение — это метод анализа данных, который автоматизирует построение аналитических моделей. "
    "Это раздел искусственного интеллекта, основанный на идее, что системы могут учиться на данных, "
    "выявлять закономерности и принимать решения с минимальным вмешательством человека. "
    "Процесс обучения начинается с наблюдений или данных, таких как примеры, непосредственный опыт или инструкции, "
    "с целью поиска закономерностей в данных и принятия более эффективных решений в будущем на основе предоставленных нами примеров."
)


class Benchmark:
    """
    Conducts a benchmark of LLM models for performance and translation quality
    via the Ollama API.
    """

    def __init__(self, models, api_url):
        self.models = models
        self.api_url = api_url
        self.results = {
            "timings": {},
            "bleu_scores": {},
            "translations": {}
        }
        # Chencherry smoothing function for BLEU, important for sentence-level scores
        self.smoothing_function = SmoothingFunction().method4

    def _translate_text(self, text, model_name, source_lang="English", target_lang="Russian"):
        """Sends text to an Ollama model for translation and returns the response."""
        prompt = (
            f"Translate the following text from {source_lang} to {target_lang}. "
            f"Provide only the translated text, without any explanations. "
            f"Text to translate: \"{text}\""
        )
        payload = {"model": model_name, "prompt": prompt, "stream": False}

        try:
            response = requests.post(self.api_url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.exceptions.RequestException as e:
            print(f"\n[ERROR] Could not connect to Ollama for model {model_name}: {e}")
            print("Please ensure Ollama is running and the model is available ('ollama run model_name').")
            return None

    def _calculate_bleu(self, reference, candidate):
        """Calculates the BLEU score between a candidate translation and a reference."""
        reference_tokens = [reference.split()]
        candidate_tokens = candidate.split()
        return sentence_bleu(reference_tokens, candidate_tokens, smoothing_function=self.smoothing_function)

    @staticmethod
    def _show_spinner(stop_event):
        """Displays a simple spinner in the console during long operations."""
        spinner = ['-', '\\', '|', '/']
        i = 0
        while not stop_event.is_set():
            sys.stdout.write(f'\r{spinner[i % len(spinner)]} Translating... ')
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write('\r' + ' ' * 20 + '\r')
        sys.stdout.flush()

    def run(self, source_text, reference_text):
        """Executes the full benchmark suite."""
        print("=" * 50 + "\n STARTING BENCHMARK ANALYSIS \n" + "=" * 50)

        component_timings = {}
        total_start_time = time.perf_counter()

        for model in self.models:
            print(f"\n--- Testing model: {model} ---")

            stop_spinner = threading.Event()
            spinner_thread = threading.Thread(target=self._show_spinner, args=(stop_spinner,))
            spinner_thread.start()

            start_time = time.perf_counter()
            translation = self._translate_text(source_text, model)
            end_time = time.perf_counter()

            stop_spinner.set()
            spinner_thread.join()

            if translation is None:
                print(f"Skipping model {model} due to an error.")
                continue

            duration = end_time - start_time
            component_timings[f"Translation ({model})"] = duration
            self.results["translations"][model] = translation

            print(f"Translation finished in: {duration:.2f} seconds.")
            print(f"Generated Translation:\n---\n{translation}\n---")

            bleu_start_time = time.perf_counter()
            bleu_score = self._calculate_bleu(reference_text, translation)
            bleu_end_time = time.perf_counter()
            component_timings[f"BLEU Calculation ({model})"] = bleu_end_time - bleu_start_time

            self.results["bleu_scores"][model] = bleu_score
            print(f"BLEU Score: {bleu_score:.4f} (calculation took {(bleu_end_time - bleu_start_time):.4f} sec.)")

        total_end_time = time.perf_counter()
        component_timings["Total Time"] = total_end_time - total_start_time
        self.results["timings"] = component_timings

        print("\n--- Final Results ---")
        for model_name, timing in self.results["timings"].items():
            if 'Translation' in model_name:
                print(f"Translation Time ({model_name.split('(')[1].split(')')[0]}): {timing:.2f} sec.")
        for model_name, score in self.results["bleu_scores"].items():
            print(f"BLEU Score ({model_name}): {score:.4f}")

    def plot_results(self):
        """Generates and displays plots visualizing the benchmark results."""
        if not self.results["timings"] or not self.results["bleu_scores"]:
            print("\nNo data available to plot.")
            return

        sns.set_theme(style="whitegrid")

        # --- Plot 1: Component Execution Time ---
        plt.figure(figsize=(12, 6))

        timings_data = self.results["timings"]
        palette = sns.color_palette("viridis", len(timings_data))

        ax1 = sns.barplot(x=list(timings_data.keys()), y=list(timings_data.values()), palette=palette)
        ax1.set_title('Performance: Component Execution Time', fontsize=16)
        ax1.set_ylabel('Time (seconds)', fontsize=12)
        ax1.set_xlabel('Component', fontsize=12)

        for container in ax1.containers:
            ax1.bar_label(container, fmt='%.2f s')

        plt.xticks(rotation=15, ha="right")
        plt.tight_layout()

        # --- Plot 2: BLEU Score Comparison ---
        plt.figure(figsize=(10, 6))

        bleu_data = self.results["bleu_scores"]

        ax2 = sns.barplot(x=list(bleu_data.keys()), y=list(bleu_data.values()), palette="plasma")
        ax2.set_title('Translation Quality: BLEU Score Comparison', fontsize=16)
        ax2.set_ylabel('BLEU Score (Higher is Better)', fontsize=12)
        ax2.set_xlabel('Model', fontsize=12)
        ax2.set_ylim(0, 1.0)

        for container in ax2.containers:
            ax2.bar_label(container, fmt='%.4f')

        plt.tight_layout()

        print("\nDisplaying plots... Close the plot windows to exit the program.")
        plt.show()


if __name__ == "__main__":
    benchmark = Benchmark(models=MODELS_TO_TEST, api_url=OLLAMA_API_URL)
    benchmark.run(source_text=SOURCE_TEXT_EN, reference_text=REFERENCE_TRANSLATION_RU)
    benchmark.plot_results()
