#!/usr/bin/env python3
"""Utility script for running gplearn-based symbolic regression classification sweeps.

Given a CSV dataset with a binary target column, this script trains a `SymbolicClassifier`
using the preset configuration (or user overrides) and exports multiple summary files
mirroring the original research workflow:

1. `all_formulas_detailed.txt`          – Ranked by accuracy and by complexity
2. `all_formulas_by_accuracy.csv`       – Tabular view sorted by accuracy
3. `all_formulas_by_complexity.csv`     – Tabular view sorted by length/depth
4. `formulas_by_accuracy_groups.txt`    – Bucketed by accuracy range with simplest formula highlighted
5. `formulas_summary_table.txt`         – Compact table for quick review

Usage example:
    python run_symbolic_regression.py data_train_for_SR.csv --target-column class --output-dir ./outputs
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd
from gplearn.genetic import SymbolicClassifier
from sklearn.metrics import accuracy_score

warnings.filterwarnings("ignore")

DEFAULT_CONFIG: Dict[str, Any] = {
    "population_size": 3000,
    "generations": 100,
    "tournament_size": 10,
    "function_set": ("add", "sub", "mul", "div"),
    "init_depth": (1, 4),
    "parsimony_coefficient": 0.01,
    "p_crossover": 0.6,
    "p_subtree_mutation": 0.15,
    "p_hoist_mutation": 0.10,
    "p_point_mutation": 0.10,
    "metric": "log loss",
    "const_range": (-2.0, 2.0),
    "verbose": 1,
    "random_state": 42,
    "n_jobs": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run gplearn symbolic regression sweep and export reports.")
    parser.add_argument("data_path", help="Path to the input CSV file.")
    parser.add_argument(
        "--target-column",
        dest="target_column",
        default="class",
        help="Name of the target column (default: class).",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Directory to store output reports. Defaults to the input file directory.",
    )
    parser.add_argument(
        "--config-json",
        dest="config_json",
        default=None,
        help="Optional path to a JSON file overriding gplearn hyperparameters.",
    )
    parser.add_argument(
        "--population-size",
        type=int,
        help="Override population size without editing JSON.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        help="Override number of generations without editing JSON.",
    )
    parser.add_argument(
        "--function-set",
        dest="function_set",
        help="Comma-separated function names to override the default function set.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        help="Override random seed for reproducibility tweaks.",
    )
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()

    if args.config_json:
        with open(args.config_json, "r", encoding="utf-8") as f:
            config.update(json.load(f))

    if args.population_size:
        config["population_size"] = args.population_size
    if args.generations:
        config["generations"] = args.generations
    if args.function_set:
        config["function_set"] = tuple(fn.strip() for fn in args.function_set.split(",") if fn.strip())
    if args.random_state is not None:
        config["random_state"] = args.random_state

    return config


def ensure_output_dir(path: str | None, data_path: str) -> Path:
    if path:
        out_dir = Path(path).expanduser().resolve()
    else:
        out_dir = Path(data_path).expanduser().resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))


def evaluate_program(program, X_array: np.ndarray, y_true: np.ndarray) -> Dict[str, Any] | None:
    try:
        y_raw = program.execute(X_array)
        if not np.isfinite(y_raw).all():
            return None
        y_prob = sigmoid(y_raw)
        y_pred = (y_prob > 0.5).astype(int)
        accuracy = accuracy_score(y_true, y_pred)
        return {
            "formula": str(program),
            "accuracy": accuracy,
            "length": program.length_,
            "depth": program.depth_,
        }
    except Exception:
        return None


def collect_programs(clf, X_array: np.ndarray, y: np.ndarray) -> List[Dict[str, Any]]:
    all_formulas: List[Dict[str, Any]] = []
    for gen_idx, generation in enumerate(clf._programs):
        if generation is None:
            continue
        for prog_idx, program in enumerate(generation):
            if program is None:
                continue
            result = evaluate_program(program, X_array, y)
            if result:
                result.update({"generation": gen_idx, "program_idx": prog_idx, "program": program})
                all_formulas.append(result)
        if (gen_idx + 1) % 10 == 0 or gen_idx == 0:
            print(f"Processed generation {gen_idx + 1}, cumulative valid programs: {len(all_formulas)}")
    print(f"Total valid programs collected: {len(all_formulas)}")
    return all_formulas


def deduplicate_formulas(all_formulas: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: Dict[str, Dict[str, Any]] = {}
    for item in all_formulas:
        formula = item["formula"]
        if formula not in unique:
            unique[formula] = item
    print(f"Unique formulas after deduplication: {len(unique)}")
    return list(unique.values())


def write_reports(formulas: List[Dict[str, Any]], output_dir: Path) -> None:
    if not formulas:
        raise RuntimeError("No valid formulas produced. Check dataset and hyperparameters.")

    formulas_by_acc = sorted(formulas, key=lambda x: (-x["accuracy"], x["length"], x["depth"]))
    formulas_by_complexity = sorted(formulas, key=lambda x: (x["length"], x["depth"], -x["accuracy"]))

    accuracies = [item["accuracy"] for item in formulas]
    lengths = [item["length"] for item in formulas]
    depths = [item["depth"] for item in formulas]

    # Detailed text report
    detailed_path = output_dir / "all_formulas_detailed.txt"
    with detailed_path.open("w", encoding="utf-8") as f:
        f.write("=" * 100 + "\n")
        f.write("gplearn 符号回归 - 所有公式详细报告\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"总公式数: {len(formulas)}\n")
        f.write(f"准确率范围: {min(accuracies):.4f} - {max(accuracies):.4f}\n")
        f.write(f"复杂度范围: 长度 {min(lengths)}-{max(lengths)}, 深度 {min(depths)}-{max(depths)}\n\n")

        f.write("=" * 100 + "\n【部分1】按准确率排序 (从高到低)\n" + "=" * 100 + "\n\n")
        for idx, item in enumerate(formulas_by_acc, 1):
            f.write(f"【第 {idx} 名】\n")
            f.write(f"  准确率: {item['accuracy']:.4f} ({item['accuracy'] * 100:.2f}%)\n")
            f.write(f"  复杂度: 长度={item['length']}, 深度={item['depth']}\n")
            f.write(f"  发现于: 第{item['generation']}代\n")
            f.write(f"  公式: {item['formula']}\n\n")

        f.write("=" * 100 + "\n【部分2】按复杂度排序 (从简单到复杂)\n" + "=" * 100 + "\n\n")
        for idx, item in enumerate(formulas_by_complexity, 1):
            f.write(f"【第 {idx} 名】\n")
            f.write(f"  复杂度: 长度={item['length']}, 深度={item['depth']}\n")
            f.write(f"  准确率: {item['accuracy']:.4f} ({item['accuracy'] * 100:.2f}%)\n")
            f.write(f"  发现于: 第{item['generation']}代\n")
            f.write(f"  公式: {item['formula']}\n\n")

    # CSV reports
    df_acc = pd.DataFrame(
        [
            {
                "rank_by_accuracy": idx,
                "formula": item["formula"],
                "accuracy": item["accuracy"],
                "length": item["length"],
                "depth": item["depth"],
                "generation": item["generation"],
            }
            for idx, item in enumerate(formulas_by_acc, 1)
        ]
    )
    df_acc.to_csv(output_dir / "all_formulas_by_accuracy.csv", index=False, encoding="utf-8")

    df_complexity = pd.DataFrame(
        [
            {
                "rank_by_complexity": idx,
                "formula": item["formula"],
                "length": item["length"],
                "depth": item["depth"],
                "accuracy": item["accuracy"],
                "generation": item["generation"],
            }
            for idx, item in enumerate(formulas_by_complexity, 1)
        ]
    )
    df_complexity.to_csv(output_dir / "all_formulas_by_complexity.csv", index=False, encoding="utf-8")

    # Accuracy groups
    groups_path = output_dir / "formulas_by_accuracy_groups.txt"
    acc_ranges = [
        (1.0, 1.0, "100%"),
        (0.96, 0.99, "96-99%"),
        (0.92, 0.95, "92-95%"),
        (0.88, 0.91, "88-91%"),
        (0.84, 0.87, "84-87%"),
        (0.80, 0.83, "80-83%"),
        (0.0, 0.79, "<80%"),
    ]

    with groups_path.open("w", encoding="utf-8") as f:
        f.write("=" * 100 + "\n公式按准确率分组\n" + "=" * 100 + "\n\n")
        for min_acc, max_acc, label in acc_ranges:
            bucket = [item for item in formulas_by_acc if min_acc <= item["accuracy"] <= max_acc]
            if not bucket:
                continue
            f.write("=" * 100 + f"\n准确率区间: {label} (共 {len(bucket)} 个公式)\n" + "=" * 100 + "\n\n")
            simplest = min(bucket, key=lambda x: (x["length"], x["depth"]))
            f.write("【最简单的公式】\n")
            f.write(f"  准确率: {simplest['accuracy']:.4f}\n")
            f.write(f"  长度: {simplest['length']}, 深度: {simplest['depth']}\n")
            f.write(f"  公式: {simplest['formula']}\n\n")
            f.write("【该组所有公式】(按复杂度排序)\n\n")
            for idx, item in enumerate(sorted(bucket, key=lambda x: (x["length"], x["depth"])), 1):
                f.write(
                    f"  {idx}. 准确率={item['accuracy']:.4f}, 长度={item['length']}, 深度={item['depth']}\n"
                )
                f.write(f"     {item['formula']}\n\n")

    # Summary table
    summary_path = output_dir / "formulas_summary_table.txt"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("=" * 130 + "\n所有公式汇总表\n" + "=" * 130 + "\n\n")
        f.write(f"{'序号':<6} {'准确率':<12} {'长度':<8} {'深度':<8} {'代':<8} {'公式'}\n")
        f.write("-" * 130 + "\n")
        for idx, item in enumerate(formulas_by_acc, 1):
            formula_display = item["formula"] if len(item["formula"]) <= 80 else item["formula"][:77] + "..."
            f.write(
                f"{idx:<6} {item['accuracy']:<12.4f} {item['length']:<8} {item['depth']:<8} {item['generation']:<8} {formula_display}\n"
            )

    print("Saved reports:")
    for filename in [
        "all_formulas_detailed.txt",
        "all_formulas_by_accuracy.csv",
        "all_formulas_by_complexity.csv",
        "formulas_by_accuracy_groups.txt",
        "formulas_summary_table.txt",
    ]:
        print(f"  - {output_dir / filename}")


def main() -> None:
    args = parse_args()
    data_path = Path(args.data_path).expanduser().resolve()
    if not data_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {data_path}")

    output_dir = ensure_output_dir(args.output_dir, str(data_path))

    print("=" * 100)
    print("gplearn 符号回归 - 全量报告生成")
    print("=" * 100)

    print("\n[1/4] 加载数据")
    df = pd.read_csv(data_path)
    if args.target_column not in df.columns:
        raise ValueError(f"Target column '{args.target_column}' not found in dataset columns: {list(df.columns)}")

    X_raw = df.drop(columns=args.target_column)
    numeric_cols = [col for col in X_raw.columns if pd.api.types.is_numeric_dtype(X_raw[col])]
    dropped_cols = [col for col in X_raw.columns if col not in numeric_cols]
    if not numeric_cols:
        raise ValueError("No numeric feature columns found after excluding the target column.")

    X = X_raw[numeric_cols].astype(float)
    y = df[args.target_column].astype(int).values
    feature_names = list(X.columns)
    X_array = X.values
    print(f"数据形状: {df.shape}, 特征数量: {len(feature_names)}, 样本数量: {len(y)}")
    if dropped_cols:
        print(f"自动忽略非数值列: {dropped_cols}")

    print("\n[2/4] 训练 gplearn 模型")
    config = load_config(args)
    config["feature_names"] = feature_names
    clf = SymbolicClassifier(**config)
    clf.fit(X_array, y)

    print("\n[3/4] 收集并去重所有程序")
    all_programs = collect_programs(clf, X_array, y)
    unique_formulas = deduplicate_formulas(all_programs)

    print("\n[4/4] 写出报告")
    write_reports(unique_formulas, output_dir)

    print("\n完成！输出目录: ", output_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断。", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n发生错误: {exc}", file=sys.stderr)
        sys.exit(1)
