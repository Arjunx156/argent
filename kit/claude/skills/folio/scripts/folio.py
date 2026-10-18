"""folio: typeset Markdown or Typst into a book-grade PDF.

    python folio.py build  DOC.md|DOC.typ [-o OUT.pdf] [--png DIR] [--keep] [--force]
    python folio.py check  FILE [FILE ...]
    python folio.py setup

build   Lint the prose (Markdown only), convert with Pandoc, compile with Typst.
        --png DIR   also render every page to DIR/page-NN.png for visual review
        --keep      keep the generated .typ next to the source
        --force     typeset even if the prose linter reports errors
check   Run the prose linter alone.
setup   Install the @local/folio Typst package and report missing tools.
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
FONTS = SKILL / "fonts"
PACKAGE_SRC = SKILL / "typst" / "folio"
PANDOC_TEMPLATE = SKILL / "pandoc" / "folio.typ"
VERSION = "1.0.0"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slop  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8")


def typst_data_dir():
    if os.name == "nt":
        return Path(os.environ["APPDATA"]) / "typst"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "typst"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "typst"


def fresh_path():
    """PATH as the registry has it now. Sessions started before an install have a stale copy."""
    if os.name != "nt":
        return os.environ.get("PATH", "")
    import winreg
    parts = []
    for hive, key in ((winreg.HKEY_CURRENT_USER, r"Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
        try:
            with winreg.OpenKey(hive, key) as k:
                parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        except OSError:
            pass
    return os.pathsep.join(parts + [os.environ.get("PATH", "")])


def need(tool):
    path = shutil.which(tool) or shutil.which(tool, path=fresh_path())
    if not path:
        sys.exit(f"folio: '{tool}' not found on PATH. Install it (winget install {tool}) and retry.")
    return path


def install_package():
    """Copy the template into Typst's local package store when it is missing or stale."""
    dest = typst_data_dir() / "packages" / "local" / "folio" / VERSION
    stale = not dest.exists() or any(
        not (dest / f.name).exists() or not filecmp.cmp(f, dest / f.name, shallow=False)
        for f in PACKAGE_SRC.iterdir()
    )
    if stale:
        dest.mkdir(parents=True, exist_ok=True)
        for f in PACKAGE_SRC.iterdir():
            shutil.copy2(f, dest / f.name)
    return dest


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    out = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        sys.exit(f"folio: {Path(cmd[0]).name} failed\n{out}")
    if out:
        print(out)


def contact_sheet(typst, main, root, out_png):
    """Every page on one image, so a whole document is checked with a single look."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        run([typst, "compile", "--root", root, "--font-path", str(FONTS), "--format", "png",
             "--ppi", "40", str(main), str(tmp / "p-{0p}.png")])
        pages = sorted(tmp.glob("p-*.png"))
        cols = 4 if len(pages) <= 16 else 6
        cells = ", ".join(f'image("{p.name}", width: 120pt)' for p in pages)
        (tmp / "sheet.typ").write_text(
            '#set page(width: auto, height: auto, margin: 6pt, fill: rgb("#9a9a9a"))\n'
            f"#grid(columns: {cols}, gutter: 6pt, {cells})\n", encoding="utf-8")
        out_png.parent.mkdir(parents=True, exist_ok=True)
        run([typst, "compile", "--root", str(tmp), "--format", "png", "--ppi", "110",
             str(tmp / "sheet.typ"), str(out_png)])
    return len(pages)


def build(args):
    src = Path(args.doc).resolve()
    if not src.exists():
        sys.exit(f"folio: no such file: {src}")
    out = Path(args.output).resolve() if args.output else src.with_suffix(".pdf")
    typst = need("typst")
    install_package()

    generated = None
    if src.suffix.lower() in (".md", ".markdown", ".txt"):
        findings = slop.lint(src)
        errors = [f for f in findings if f[0] == "error"]
        for severity, line, rule, detail in findings:
            print(f"{src.name}:{line}: {severity}: [{rule}] {detail}")
        if errors and not args.force:
            sys.exit(f"folio: {len(errors)} prose error(s). Fix them, or pass --force.")
        pandoc = need("pandoc")
        generated = src.with_name(f".{src.stem}.folio.typ")
        run([pandoc, str(src), "--from", "markdown+smart", "--to", "typst",
             "--template", str(PANDOC_TEMPLATE), "--wrap=none", "-o", str(generated)])
        main = generated
    elif src.suffix.lower() == ".typ":
        main = src
    else:
        sys.exit("folio: expected a .md or .typ file")

    root = args.root or str(src.anchor)
    try:
        run([typst, "compile", "--root", root, "--font-path", str(FONTS), str(main), str(out)])
        print(f"pdf   {out}")
        if args.png:
            png_dir = Path(args.png).resolve()
            png_dir.mkdir(parents=True, exist_ok=True)
            for old in png_dir.glob("page-*.png"):
                old.unlink()
            run([typst, "compile", "--root", root, "--font-path", str(FONTS), "--format", "png",
                 "--ppi", str(args.ppi), str(main), str(png_dir / "page-{0p}.png")])
            pages = sorted(png_dir.glob("page-*.png"))
            print(f"png   {len(pages)} pages in {png_dir}")
        if args.sheet:
            n = contact_sheet(typst, main, root, Path(args.sheet).resolve())
            print(f"sheet {n} pages on one image: {Path(args.sheet).resolve()}")
    finally:
        if generated and generated.exists() and not args.keep:
            generated.unlink()


def setup(_args):
    dest = install_package()
    print(f"package  @local/folio:{VERSION} -> {dest}")
    for tool in ("typst", "pandoc"):
        print(f"{tool:8} {shutil.which(tool) or shutil.which(tool, path=fresh_path()) or 'MISSING'}")
    print(f"fonts    {FONTS}")


def main():
    parser = argparse.ArgumentParser(prog="folio", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("doc")
    b.add_argument("-o", "--output")
    b.add_argument("--png", metavar="DIR")
    b.add_argument("--sheet", metavar="FILE.png", help="every page on one image, for a single visual check")
    b.add_argument("--ppi", type=int, default=70)
    b.add_argument("--root", help="Typst project root (default: the drive of DOC)")
    b.add_argument("--keep", action="store_true")
    b.add_argument("--force", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("files", nargs="+")
    sub.add_parser("setup")
    args = parser.parse_args()
    if args.cmd == "build":
        build(args)
    elif args.cmd == "check":
        sys.exit(slop.main(args.files))
    else:
        setup(args)


if __name__ == "__main__":
    main()
