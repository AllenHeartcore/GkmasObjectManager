import asyncio
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path

from cryptography.hazmat.primitives.hashes import SHA256, Hash
from tqdm import tqdm


def sha256sum(path: Path, prog: tqdm) -> str:
    data = path.read_bytes()
    digest = Hash(SHA256())
    digest.update(data)
    prog.update(1)
    return digest.finalize().hex()


async def sha256sum_all(paths: list[Path]) -> list[str]:
    with tqdm(total=len(paths), desc="Hashing files") as prog:
        return await asyncio.gather(
            *[asyncio.to_thread(sha256sum, path, prog) for path in paths]
        )


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("cwd", type=str)
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()

    # Deduplicate img_general_cidol

    cwd = Path(args.cwd) / "img_general_cidol"
    paths = list(cwd.rglob("*.png"))
    hashes = asyncio.run(sha256sum_all(paths))

    hash2path = defaultdict(list)
    for h, p in zip(hashes, paths):
        hash2path[h].append(p)

    dup_hashes = [h for h, c in Counter(hashes).items() if c > 1]
    for dup_hash in dup_hashes:

        dup = hash2path[dup_hash]
        assert len(dup) == 2
        assert dup[0].stem.replace("_0-full", "_1-full") == dup[1].stem

        if args.dry:
            print(f'Would delete "{dup[1]}"')
        else:
            dup[1].unlink()
            print(f'Deleted "{dup[1]}"')
            new_name = dup[0].name.replace("_0-full", "-full")
            dup[0].rename(dup[0].with_name(new_name))

    # Categorize img_general_music_jacket

    cwd = Path(args.cwd) / "img_general__music_jacket"
    paths = list(cwd.rglob("*.png"))

    for path in paths:

        if path.stem.count("-") < 2:
            continue

        _a, b, c, *_ = path.stem.split("-")
        a = _a.split("_")[-1]
        if a == "all":
            if c == "inst":
                cat = f"{a}-{b}"
            else:
                cat = f"{a}-{c}"
        elif a == "char":
            cat = f"{a}-{b}"
        elif a == "unit":
            cat = a
        else:
            continue

        new_dir = path.parent / cat
        new_dir.mkdir(exist_ok=True)
        new_path = new_dir / path.name

        if args.dry:
            print(f'Would move "{path.name}" into "{cat}"')
        else:
            path.rename(new_path)
            print(f'Moved "{path.name}" into "{cat}"')
