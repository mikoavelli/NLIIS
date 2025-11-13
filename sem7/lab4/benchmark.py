import requests
import time
import matplotlib.pyplot as plt
import seaborn as sns
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
import threading
import sys
import re

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODELS_TO_TEST = ['llama3.1:8b', 'llama3.2:1b']
WORD_TRANSLATION_MODEL = 'llama3.1:8b'

SOURCE_TEXT_EN = (
    "Machine learning is a method of data analysis that automates analytical model building. "
    "It is a branch of artificial intelligence based on the idea that systems can learn from data, "
    "identify patterns and make decisions with minimal human intervention. "
    "The process of learning begins with observations or data, such as examples, direct experience, or instruction, "
    "in order to look for patterns in data and make better decisions in the future based on the examples that we provide."
)

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
        except requests.exceptions.RequestException:
            return None

    def _calculate_bleu(self, reference, candidate):
        """Calculates the BLEU score between a candidate translation and a reference."""
        reference_tokens = [reference.split()]
        candidate_tokens = candidate.split()
        return sentence_bleu(reference_tokens, candidate_tokens, smoothing_function=self.smoothing_function)

    @staticmethod
    def _show_spinner(stop_event, message="Processing..."):
        """Displays a simple spinner in the console during long operations."""
        spinner = ['-', '\\', '|', '/']
        i = 0
        while not stop_event.is_set():
            sys.stdout.write(f'\r{spinner[i % len(spinner)]} {message} ')
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write('\r' + ' ' * (len(message) + 5) + '\r')
        sys.stdout.flush()

    def run(self, source_text, reference_text):
        """Executes the full benchmark suite with updated performance metrics."""
        print("=" * 50 + "\n STARTING BENCHMARK ANALYSIS \n" + "=" * 50)

        performance_timings = {}

        for model in self.models:
            print(f"\n--- Testing Full Text Translation: {model} ---")

            stop_spinner = threading.Event()
            spinner_thread = threading.Thread(target=self._show_spinner,
                                              args=(stop_spinner, f"Translating with {model}..."))
            spinner_thread.start()

            start_time = time.perf_counter()
            translation = self._translate_text(source_text, model)
            end_time = time.perf_counter()

            stop_spinner.set()
            spinner_thread.join()

            if translation is None:
                print(f"\n[ERROR] Could not get translation from {model}. Skipping.")
                continue

            duration = end_time - start_time
            performance_timings[f"Full Text ({model})"] = duration
            self.results["translations"][model] = translation

            print(f"Translation finished in: {duration:.2f} seconds.")

            bleu_score = self._calculate_bleu(reference_text, translation)
            self.results["bleu_scores"][model] = bleu_score
            print(f"BLEU Score: {bleu_score:.4f}")

        print(f"\n--- Testing Word-by-Word Translation ({WORD_TRANSLATION_MODEL}) ---")
        unique_words = sorted(list(set(re.findall(r'\b\w+\b', source_text.lower()))))
        print(f"Found {len(unique_words)} unique words to translate.")

        stop_spinner = threading.Event()
        spinner_thread = threading.Thread(target=self._show_spinner, args=(stop_spinner, "Translating words..."))
        spinner_thread.start()

        start_time_words = time.perf_counter()
        for word in unique_words:
            self._translate_text(word, WORD_TRANSLATION_MODEL)
        end_time_words = time.perf_counter()

        stop_spinner.set()
        spinner_thread.join()

        word_duration = end_time_words - start_time_words
        performance_timings[f"Word-by-Word ({len(unique_words)} words)"] = word_duration
        print(f"Finished in: {word_duration:.2f} seconds.")

        self.results["timings"] = performance_timings

        print("\n--- Final Results ---")
        for component, timing in self.results["timings"].items():
            print(f"Performance ({component}): {timing:.2f} sec.")
        for model_name, score in self.results["bleu_scores"].items():
            print(f"Quality BLEU Score ({model_name}): {score:.4f}")

    def plot_results(self):
        """Generates and displays plots visualizing the benchmark results."""
        if not self.results["timings"] or not self.results["bleu_scores"]:
            print("\nNo data available to plot.")
            return

        sns.set_theme(style="whitegrid")

        plt.figure(figsize=(10, 6))

        timings_data = self.results["timings"]

        ax1 = sns.barplot(
            x=list(timings_data.keys()),
            y=list(timings_data.values()),
            hue=list(timings_data.keys()),
            palette="viridis",
            legend=False
        )
        ax1.set_title('Performance: Translation Time', fontsize=16)
        ax1.set_ylabel('Time (seconds)', fontsize=12)
        ax1.set_xlabel('Benchmark Component', fontsize=12)

        for container in ax1.containers:
            ax1.bar_label(container, fmt='%.2f s')

        plt.xticks(rotation=10, ha="right")
        plt.tight_layout()

        plt.figure(figsize=(10, 6))

        bleu_data = self.results["bleu_scores"]

        ax2 = sns.barplot(
            x=list(bleu_data.keys()),
            y=list(bleu_data.values()),
            hue=list(bleu_data.keys()),
            palette="plasma",
            legend=False
        )
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
