import argparse

import sample.dataset.dataset_pipeline as dp
import sample.training.train_classifier as tc


def main() -> None:
    parser = argparse.ArgumentParser(description="Run classifiers")
    parser.add_argument('model_type', type=str, help='Type of the model (gat, gcn, transformer, sage, fcnn, dt, rf')
    args = parser.parse_args()
    
    dp.main()
    tc.main(args)


if __name__ == '__main__':
    main()