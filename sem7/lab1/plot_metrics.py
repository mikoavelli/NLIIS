# plot_metrics.py

import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import os

# Create a directory to store plots if it doesn't exist
PLOTS_DIR = "evaluation_plots"
if not os.path.exists(PLOTS_DIR):
    os.makedirs(PLOTS_DIR)


def plot_line_charts(evaluation_data):
    """
    Creates and saves line charts for key metrics, similar to the example.
    """
    print("Generating line charts for individual metrics...")

    # Prepare data for DataFrame
    records = []
    queries = [item['query'] for item in evaluation_data['query_results']]

    for item in evaluation_data['query_results']:
        query_label = item['query']
        metrics_data = item['metrics']
        # Add all scalar metrics to the record
        record = {'query': query_label}
        for metric, value in metrics_data.items():
            if isinstance(value, (int, float)):  # Ensure we only get numbers
                record[metric] = value
        records.append(record)

    df = pd.DataFrame.from_records(records)

    # Use shortened, more readable query labels for the x-axis ticks
    df['short_query'] = df['query'].apply(lambda q: (q[:25] + '...') if len(q) > 28 else q)

    metrics_to_plot = {
        'precision': 'Precision',
        'recall': 'Recall',
        'f1_score': 'F1-Score',
        'average_precision': 'Average Precision',
        'precision_at_5': 'Precision@5',
        'precision_at_10': 'Precision@10'
    }

    # Set a professional style for the plots
    sns.set_theme(style="whitegrid")

    for metric_key, metric_title in metrics_to_plot.items():
        plt.figure(figsize=(12, 7))

        # Create the line plot
        lineplot = sns.lineplot(
            x='short_query',
            y=metric_key,
            data=df,
            marker='o',  # Add markers for each point
            markersize=8,  # Marker size
            linestyle='-',  # Solid line
            err_style=None  # No error bars needed for this data
        )

        plt.title(f'Metric: {metric_title}', fontsize=18, pad=20)
        plt.xlabel("Search Query", fontsize=14, labelpad=15)
        plt.ylabel("Score", fontsize=14, labelpad=15)
        plt.xticks(rotation=15, ha='right', fontsize=11)
        plt.yticks(fontsize=11)
        plt.ylim(-0.05, 1.05)  # Set y-axis from -0.05 to 1.05 for better visuals
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)

        # Add value labels on top of each marker
        for index, row in df.iterrows():
            plt.text(row['short_query'], row[metric_key] + 0.03, f"{row[metric_key]:.2f}",
                     ha='center', color='black', fontsize=10)

        plt.tight_layout()
        output_filename = os.path.join(PLOTS_DIR, f'plot_{metric_key}.png')
        plt.savefig(output_filename)
        print(f"  > Saved '{output_filename}'")
        plt.close()


def plot_precision_recall_curve(evaluation_data):
    """
    Calculates and plots the averaged 11-Point Precision-Recall Curve.
    """
    print("\nGenerating 11-Point Precision-Recall Curve...")

    num_queries = len(evaluation_data['query_results'])
    if num_queries == 0:
        print("  > No query results to plot.")
        return

    sum_of_points = np.array([0.0] * 11)
    for item in evaluation_data['query_results']:
        sum_of_points += np.array(item['metrics']['interpolated_precision_points'])

    avg_points = sum_of_points / num_queries
    recall_levels = [i / 10.0 for i in range(11)]

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 8))

    # Plot the interpolated (stepped) curve
    plt.step(recall_levels, avg_points, where='post', color='darkblue', linewidth=2, label='Interpolated Precision')
    # Add markers at each point
    plt.plot(recall_levels, avg_points, 'o', color='red', markersize=8)

    plt.title('11-Point Interpolated Precision-Recall Curve (Averaged)', fontsize=18, pad=20)
    plt.xlabel('Recall', fontsize=14, labelpad=15)
    plt.ylabel('Interpolated Precision', fontsize=14, labelpad=15)
    plt.xlim(-0.05, 1.05)
    plt.ylim(-0.05, 1.05)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.xticks(recall_levels, fontsize=11)
    plt.yticks(recall_levels, fontsize=11)

    # Annotate each point
    for i, txt in enumerate(avg_points):
        plt.annotate(f'{txt:.2f}', (recall_levels[i], avg_points[i]), textcoords="offset points", xytext=(0, 10),
                     ha='center')

    plt.legend()
    plt.tight_layout()
    output_filename = os.path.join(PLOTS_DIR, 'plot_precision_recall_curve.png')
    plt.savefig(output_filename)
    print(f"  > Saved '{output_filename}'")
    plt.close()


def main():
    """Main function to load results and generate all plots."""
    results_file = 'evaluation_results.json'
    try:
        with open(results_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: '{results_file}' not found.")
        print("Please run 'python evaluate.py' first to generate the results file.")
        return

    plot_line_charts(data)
    plot_precision_recall_curve(data)

    print(f"\nAll plots have been generated and saved to the '{PLOTS_DIR}/' directory.")


if __name__ == '__main__':
    main()