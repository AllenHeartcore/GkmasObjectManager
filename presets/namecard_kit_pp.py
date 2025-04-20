from sys import argv
from pathlib import Path


cat_instrs = [
    ("produce/skillcard", lambda s: s.split("_")[-2]),
]


if __name__ == "__main__":

    root = argv[1]

    for subdir, cat_func in cat_instrs:
        parent = Path(root, subdir)

        for f in parent.iterdir():
            cat = cat_func(f.name)
            (parent / cat).mkdir(parents=True, exist_ok=True)
            f.rename(parent / cat / f.name)
