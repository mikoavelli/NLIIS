# --- START OF FILE benchmark.py ---

import time
import json
import spacy
import statistics
import random
# Импортируем matplotlib
try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("\n--- Предупреждение: Библиотека matplotlib не найдена. ---")
    print("Графики не будут построены.")
    print("Установите её: pip install matplotlib")
    print("-" * 55 + "\n")

from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token

# --- Конфигурация Бенчмарка ---
SOURCES_JSON_PATH = "sources.json"
NUM_TEXTS_TO_BENCHMARK = 15 # Увеличим немного для более показательных графиков
NUM_RUNS = 1                # Для графиков часто достаточно одного прогона
SPACY_MODEL = 'en_core_web_sm'
MAX_TEXTS_ON_BAR_CHART = 30 # Ограничение для читаемости бар-чарта
# ---

def load_texts(filepath, num_texts):
    """Загружает тексты из sources.json."""
    print(f"Загрузка текстов из {filepath}...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            sources = json.load(f)
    except FileNotFoundError:
        print(f"Ошибка: Файл {filepath} не найден.")
        return None
    except json.JSONDecodeError:
        print(f"Ошибка: Не удалось декодировать JSON из файла {filepath}.")
        return None

    texts = []
    for source_id, source_data in sources.items():
        text = source_data.get("text")
        title = source_data.get("title", f"ID: {source_id}") # Получаем title
        if text:
            # Сохраняем ID, текст и title
            texts.append({"id": source_id, "content": text, "title": title})
        else:
            print(f"Предупреждение: Пустой текст для ID {source_id}")

    if not texts:
        print("Ошибка: Не найдено текстов для бенчмарка.")
        return None

    if num_texts > 0 and num_texts < len(texts):
        print(f"Выбрано {num_texts} случайных текстов для бенчмарка.")
        return random.sample(texts, num_texts)
    else:
        print(f"Используются все {len(texts)} текстов для бенчмарка.")
        return texts

def benchmark_run(nlp, texts_data):
    """Выполняет один прогон бенчмарка для заданного списка текстов."""
    results = []
    total_tokens = 0

    print(f"Начало обработки {len(texts_data)} текстов...")
    progress_interval = max(1, len(texts_data) // 20) # Обновляем прогресс примерно 20 раз

    for i, text_info in enumerate(texts_data):
        text_id = text_info["id"]
        text_content = text_info["content"]
        text_title = text_info["title"] # Используем title

        if (i + 1) % progress_interval == 0 or i == len(texts_data) - 1:
             print(f"  Обработка текста {i+1}/{len(texts_data)} (ID: {text_id})...", end='\r')

        # 1. Замер времени обработки spaCy
        start_time = time.perf_counter()
        try:
            doc = nlp(text_content)
        except Exception as e:
             print(f"\nОшибка spaCy (ID {text_id}): {e}")
             continue
        spacy_duration = time.perf_counter() - start_time
        current_tokens = len(doc)
        total_tokens += current_tokens

        # 2. Замер времени извлечения признаков
        start_time = time.perf_counter()
        # extracted_features = [] # Нам не нужно сохранять признаки для бенчмарка
        try:
            # Просто итерируем и выполняем базовые операции
            for token in doc:
                _ = token.text.lower()
                _ = token.lemma_
                _ = token.pos_
                # Можно добавить больше операций, если они есть в analyze.py
                # morph = beautiful_morph(token.morph.to_dict())
                # cleaned = clean_token(token.text)
                # pos_tag = POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)
                # dep = token.dep_
        except Exception as e:
            print(f"\nОшибка извлечения признаков (ID {text_id}): {e}")
        feature_duration = time.perf_counter() - start_time

        results.append({
            "id": text_id,
            "title": text_title, # Добавляем title
            "length": len(text_content),
            "tokens": current_tokens,
            "spacy_time": spacy_duration,
            "feature_time": feature_duration,
            "total_time": spacy_duration + feature_duration
        })

    print("\n  Прогон завершен.")
    return results, total_tokens

# --- Функции для построения графиков ---

def plot_time_per_text(run_results, max_texts=MAX_TEXTS_ON_BAR_CHART):
    """Строит столбчатую диаграмму времени обработки для каждого текста."""
    if not MATPLOTLIB_AVAILABLE: return
    if not run_results: return

    # Ограничиваем количество текстов на графике
    results_to_plot = run_results[:max_texts]
    num_bars = len(results_to_plot)

    # Используем title или ID для меток оси X
    labels = [res.get('title', res['id']) for res in results_to_plot]
    spacy_times = [res['spacy_time'] for res in results_to_plot]
    feature_times = [res['feature_time'] for res in results_to_plot]

    x = range(num_bars)

    fig, ax = plt.subplots(figsize=(max(10, num_bars * 0.5), 6)) # Динамический размер

    # Строим столбцы для времени spaCy
    bars1 = ax.bar(x, spacy_times, label='spaCy Processing (nlp(text))')
    # Строим столбцы для времени извлечения признаков поверх spaCy
    bars2 = ax.bar(x, feature_times, bottom=spacy_times, label='Feature Extraction (iteration)')

    ax.set_ylabel('Time (seconds)')
    ax.set_title(f'Processing Time per Text (First {num_bars} Texts)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=80, ha='right', fontsize=8) # Поворот меток
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.3f')) # Формат оси Y

    # Добавляем значения на верхушку столбцов (опционально, может быть грязно)
    # for i, bar_s in enumerate(bars1):
    #     total_h = bar_s.get_height() + bars2[i].get_height()
    #     ax.text(bar_s.get_x() + bar_s.get_width() / 2., total_h,
    #             f'{total_h:.3f}', ha='center', va='bottom', fontsize=7, rotation=90)

    plt.tight_layout() # Подгоняем расположение элементов
    # plt.savefig("benchmark_time_per_text.png") # Опция сохранения

def plot_time_distribution(all_times_dict):
    """Строит box plot для распределения времени."""
    if not MATPLOTLIB_AVAILABLE: return
    if not all_times_dict: return

    labels = list(all_times_dict.keys())
    data_to_plot = list(all_times_dict.values())

    # Проверяем, что есть данные для отрисовки
    if not any(data_to_plot):
        print("Нет данных для построения графика распределения времени.")
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.boxplot(data_to_plot, labels=labels, showfliers=True) # showfliers=False скроет выбросы
    ax.set_ylabel('Time (seconds)')
    ax.set_title('Distribution of Processing Times Across All Texts & Runs')
    ax.yaxis.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.5)

    plt.tight_layout()
    # plt.savefig("benchmark_time_distribution.png")

def plot_time_vs_tokens(run_results):
    """Строит диаграмму рассеяния: время обработки vs количество токенов."""
    if not MATPLOTLIB_AVAILABLE: return
    if not run_results: return

    tokens = [res['tokens'] for res in run_results]
    total_times = [res['total_time'] for res in run_results]

    if not tokens or not total_times:
        print("Нет данных для построения графика время vs токены.")
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(tokens, total_times, alpha=0.6, edgecolors='w', s=50) # s - размер точек
    ax.set_xlabel('Number of Tokens')
    ax.set_ylabel('Total Processing Time (seconds)')
    ax.set_title('Processing Time vs. Number of Tokens per Text')
    ax.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.5)

    # Линия тренда (опционально)
    try:
        import numpy as np
        coeffs = np.polyfit(tokens, total_times, 1) # Линейная аппроксимация
        poly1d_fn = np.poly1d(coeffs)
        ax.plot(sorted(tokens), poly1d_fn(sorted(tokens)), '--r', label=f'Trend (y={coeffs[0]:.2e}x+{coeffs[1]:.3f})')
        ax.legend()
    except ImportError:
        print("Numpy не найден, линия тренда не будет построена. Установите: pip install numpy")
    except Exception as e:
        print(f"Не удалось построить линию тренда: {e}")


    plt.tight_layout()
    # plt.savefig("benchmark_time_vs_tokens.png")

# --- Основная часть скрипта ---
if __name__ == "__main__":
    print("--- Запуск Бенчмарка NLP Обработки ---")

    # 1. Загрузка модели spaCy
    print(f"Загрузка модели spaCy '{SPACY_MODEL}'...")
    start_load_time = time.perf_counter()
    try:
        nlp_model = spacy.load(SPACY_MODEL)
        load_duration = time.perf_counter() - start_load_time
        print(f"Модель загружена за {load_duration:.4f} сек.")
    except OSError:
        print(f"\n!!! Ошибка: Модель spaCy '{SPACY_MODEL}' не найдена...")
        exit()

    # 2. Загрузка текстов
    texts_to_process = load_texts(SOURCES_JSON_PATH, NUM_TEXTS_TO_BENCHMARK)
    if not texts_to_process:
        exit()

    num_texts = len(texts_to_process)
    all_run_results = []
    total_tokens_all_runs = []

    # 3. Выполнение бенчмарка
    print(f"\nВыполнение бенчмарка (Прогонов: {NUM_RUNS}, Текстов за прогон: {num_texts})...")
    total_start_time = time.perf_counter() # Общее время выполнения
    for run in range(NUM_RUNS):
        print(f"--- Прогон {run + 1}/{NUM_RUNS} ---")
        run_results, run_tokens = benchmark_run(nlp_model, texts_to_process)
        if not run_results:
            print(f"Ошибка в прогоне {run + 1}, прерывание.")
            exit()
        all_run_results.append(run_results)
        total_tokens_all_runs.append(run_tokens)

    total_execution_time = time.perf_counter() - total_start_time
    print("\n--- Бенчмарк Завершен ---")

    # 4. Агрегация результатов
    aggregated_spacy_times = []
    aggregated_feature_times = []
    aggregated_total_times = []
    aggregated_tokens = []
    total_docs_processed = 0

    for run_res in all_run_results:
        total_docs_processed += len(run_res)
        aggregated_spacy_times.extend([r['spacy_time'] for r in run_res])
        aggregated_feature_times.extend([r['feature_time'] for r in run_res])
        aggregated_total_times.extend([r['total_time'] for r in run_res])
        # Токены берем только из первого прогона для графиков vs токены
        if not aggregated_tokens:
             aggregated_tokens = [r['tokens'] for r in run_res]


    # 5. Вывод текстовой статистики
    if not aggregated_total_times:
        print("Нет данных для анализа.")
        exit()

    total_tokens_processed = sum(total_tokens_all_runs)
    avg_spacy_time = statistics.mean(aggregated_spacy_times)
    avg_feature_time = statistics.mean(aggregated_feature_times)
    avg_total_time = statistics.mean(aggregated_total_times)

    stdev_spacy_time = statistics.stdev(aggregated_spacy_times) if len(aggregated_spacy_times) > 1 else 0
    stdev_feature_time = statistics.stdev(aggregated_feature_times) if len(aggregated_feature_times) > 1 else 0
    stdev_total_time = statistics.stdev(aggregated_total_times) if len(aggregated_total_times) > 1 else 0

    print("\n--- Статистика по всем прогонам ---")
    print(f"Модель spaCy:             {SPACY_MODEL}")
    print(f"Количество прогонов:      {NUM_RUNS}")
    print(f"Текстов за прогон:        {num_texts}")
    print(f"Всего обработано текстов: {total_docs_processed}")
    print(f"Всего обработано токенов: {total_tokens_processed}")
    print(f"Общее время выполнения:   {total_execution_time:.4f} сек") # Используем общее время
    print("-" * 30)
    print("Среднее время на 1 текст:")
    print(f"  - spaCy обработка:    {avg_spacy_time:.6f} сек (± {stdev_spacy_time:.6f})")
    print(f"  - Извлечение признаков: {avg_feature_time:.6f} сек (± {stdev_feature_time:.6f})")
    print(f"  - Общее время:          {avg_total_time:.6f} сек (± {stdev_total_time:.6f})")
    print("-" * 30)

    if total_tokens_processed > 0 and total_execution_time > 0:
         tokens_per_sec = total_tokens_processed / total_execution_time
         print(f"Скорость обработки:       {tokens_per_sec:.2f} токенов/сек")
         total_pure_spacy_time = sum(aggregated_spacy_times)
         if total_pure_spacy_time > 0:
             spacy_tokens_per_sec = total_tokens_processed / total_pure_spacy_time
             print(f"Скорость spaCy обработки: {spacy_tokens_per_sec:.2f} токенов/сек")
    else:
         print("Недостаточно данных для расчета скорости обработки.")

    # 6. Построение графиков
    if MATPLOTLIB_AVAILABLE:
        print("\nПостроение графиков...")
        try:
            # График времени по текстам (из первого прогона)
            plot_time_per_text(all_run_results[0])

            # График распределения времени (по всем данным)
            times_dict_for_boxplot = {
                'spaCy Processing': aggregated_spacy_times,
                'Feature Extraction': aggregated_feature_times,
                'Total Time': aggregated_total_times
            }
            plot_time_distribution(times_dict_for_boxplot)

            # График время vs токены (из первого прогона)
            plot_time_vs_tokens(all_run_results[0])

            # Показать все графики
            print("Окна с графиками могут быть позади других окон.")
            plt.show()
        except Exception as e:
            print(f"\n--- Ошибка при построении графиков: {e} ---")
            print("Проверьте установку matplotlib и наличие данных.")
    else:
        print("\nГрафики не будут построены, так как matplotlib не доступен.")


# --- END OF FILE benchmark.py ---