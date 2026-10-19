import argparse
import json
from pathlib import Path
from rigplan.data import ingest
from rigplan.pipeline import run


def main():
    parser = argparse.ArgumentParser(description="RigPlan experimental-design workbench")
    parser.add_argument("command", choices=["ingest", "benchmark", "study"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--budget", type=int, default=60)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--random-runs", type=int, default=20)
    args = parser.parse_args()
    if args.command == "ingest":
        print(ingest(args.root).shape)
    elif args.command == "study":
        from rigplan.study import run_study
        print(json.dumps(run_study(args.root), indent=2))
    else:
        print(json.dumps(run(args.root, args.budget, args.replicates, args.random_runs), indent=2))


if __name__ == "__main__":
    main()
