from dataclasses import dataclass


@dataclass
class TrainingConfig:
    dataset_path: str = "data/golden_set.csv"
    target_column: str = "label"
    text_column: str = "response"


def main() -> None:
    config = TrainingConfig()
    print("EvalForge quality model scaffold")
    print(f"Dataset path: {config.dataset_path}")
    print("Next step: load data, extract features, train baseline classifier, log metrics.")


if __name__ == "__main__":
    main()

