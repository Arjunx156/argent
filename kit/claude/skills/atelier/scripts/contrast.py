"""wcag contrast between two hex colors. usage: contrast.py FG BG"""
import sys


def luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    # srgb -> linear, per wcag
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, b = sorted((luminance(sys.argv[1]), luminance(sys.argv[2])), reverse=True)
    ratio = (a + 0.05) / (b + 0.05)
    verdict = "AAA" if ratio >= 7 else "AA" if ratio >= 4.5 else "AA large only" if ratio >= 3 else "fail"
    print(f"{ratio:.2f}:1  {verdict}")


if __name__ == "__main__":
    main()
