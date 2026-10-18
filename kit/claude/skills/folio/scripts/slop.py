"""Prose linter: catches the tells of machine-written text before they reach a page.

    python slop.py FILE [FILE ...]      exit 1 if any error is found

Works on Markdown, Typst or plain text. Code blocks, inline code, URLs and
front matter are ignored. Errors must be fixed; warnings deserve a second look.
"""
import re
import sys
from pathlib import Path

# phrases that give away generated text. regexes, case-insensitive, whole words
ERROR_PHRASES = [
    r"delv(e|es|ed|ing)", r"tapestr(y|ies)", r"testament to", r"in today'?s \w+ (world|landscape|age|era)",
    r"ever[- ](evolving|changing)", r"navigat(e|es|ing) the (complex\w*|landscape|world|intricacies)",
    r"unlock(s|ing)? (the|its|their|your) (full )?(power|potential)", r"unleash\w*",
    r"harness(es|ing)? the power", r"game[- ]chang(er|ing)", r"seamless(ly)?", r"cutting[- ]edge",
    r"it'?s (important|worth|crucial|essential) (to note|noting|to remember|to understand)",
    r"it is (important|worth|crucial|essential) (to note|noting|to remember)",
    r"in conclusion", r"in summary", r"to sum (it )?up", r"embark(s|ed|ing)?", r"realms?",
    r"(let'?s )?dive (deep )?into", r"deep[- ]dive", r"plethora", r"myriad", r"a symphony of",
    r"boasts?", r"vibrant", r"bustling", r"meticulous(ly)?",
    r"supercharg\w*", r"revolutioni[sz]\w*", r"transformative", r"synerg(y|ies|istic)", r"holistic",
    r"empower\w*", r"whether you'?re an? ", r"look no further", r"buckle up", r"here'?s the (thing|kicker|catch)",
    r"in the (world|realm) of", r"when it comes to", r"at the end of the day", r"stands as an?",
    r"(isn'?t|is not|aren'?t|are not|wasn'?t|was not) (just|merely|simply|only) (a|an|about)\b",
    r"not (just|merely) [^.]{1,60}, (it'?s|but)", r"i hope this helps", r"great question", r"as an ai",
    r"embrac(e|es|ing) the", r"foster(s|ing)?", r"intricate\w*", r"pivotal", r"paramount", r"furthermore",
    r"moreover", r"treasure trove", r"nestled", r"labyrinth\w*", r"beacon", r"crucible", r"unparalleled",
    r"(rich|diverse) (history|heritage|tapestry)", r"journey of", r"elevat(e|es|ing) (your|our)", r"elevated (experience|game|workflow)", r"resonat(e|es|ing)",
    r"a (powerful|robust|versatile) (tool|solution|framework|platform) (for|that)",
    r"the (key|secret) to (success|unlocking)", r"(fast|rapidly)[- ]paced",
]

# fine in moderation, usually filler
WARN_PHRASES = [
    r"leverag(e|es|ed|ing)", r"robust(ly|ness)?", r"streamlin\w*", r"utili[sz](e|es|ed|ing|ation)",
    r"facilitat\w*", r"in order to", r"crucial(ly)?", r"essential(ly)?", r"comprehensive", r"nuanced",
    r"additionally", r"ultimately", r"notably", r"importantly", r"basically", r"actually", r"truly",
    r"incredibly", r"extremely", r"various", r"numerous", r"plays? a (key|vital|crucial|pivotal) role",
    r"a wide (range|variety|array) of", r"(key|important) (considerations|takeaways)", r"best practices",
    r"world[- ]class", r"next[- ]level", r"state[- ]of[- ]the[- ]art", r"innovative",
]

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF\U00002B00-\U00002BFF️]"
)
BOLD_LABEL_BULLET = re.compile(r"^\s*([-*+]|\d+[.)])\s+(\*\*|__)[^*_]{1,60}(\*\*|__)\s*[:—–-]")
BULLET = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
HEADING = re.compile(r"^\s*(#{1,6}|={1,6})\s+(.*)$")
URL = re.compile(r"https?://\S+")
INLINE_CODE = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^\s*(```|~~~)")


def _compile(patterns):
    return [(p, re.compile(r"(?<![\w-])(?:" + p + r")(?![\w-])", re.IGNORECASE)) for p in patterns]


ERRORS = _compile(ERROR_PHRASES)
WARNS = _compile(WARN_PHRASES)


def prose_lines(text):
    """Yield (line_no, line) for lines that are prose, skipping code and front matter."""
    lines = text.splitlines()
    in_fence = False
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                start = i + 1
                break
    for i in range(start, len(lines)):
        line = lines[i]
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith("    ") and not BULLET.match(line):
            continue
        yield i + 1, URL.sub("", INLINE_CODE.sub("", line))


def lint(path):
    text = Path(path).read_text(encoding="utf-8")
    found = []  # (severity, line, rule, detail)
    words = 0
    em_dashes = 0
    bullets = 0
    bold_bullets = 0
    prose = 0

    for n, line in prose_lines(text):
        stripped = line.strip()
        if not stripped:
            continue
        words += len(stripped.split())
        dashes = line.count("—") + len(re.findall(r"(?<=\w) ?--- ?(?=\w)", line))
        em_dashes += dashes
        if dashes >= 2:
            found.append(("warn", n, "em-dash", f"{dashes} em dashes in one line; use commas, colons or full stops"))

        heading = HEADING.match(line)
        if BULLET.match(line):
            bullets += 1
            if BOLD_LABEL_BULLET.match(line):
                bold_bullets += 1
        elif not heading:
            prose += 1

        if EMOJI.search(line):
            found.append(("error", n, "emoji", "no emoji or pictographic symbols in documents"))
        if heading and heading.group(2).rstrip().endswith(":"):
            found.append(("warn", n, "heading", "heading ends with a colon"))
        if "!" in re.sub(r"!\[", "", line) and not heading:
            found.append(("warn", n, "exclaim", "exclamation mark; let the content carry the weight"))
        for pattern, rx in ERRORS:
            m = rx.search(line)
            if m:
                found.append(("error", n, "phrase", f'"{m.group(0)}"'))
        for pattern, rx in WARNS:
            m = rx.search(line)
            if m:
                found.append(("warn", n, "filler", f'"{m.group(0)}"'))

    if words and em_dashes / words > 1 / 250:
        found.append(("error", 0, "em-dash",
                      f"{em_dashes} em dashes in {words} words (limit 1 per 250); rewrite most of them"))
    if bold_bullets > 2:
        found.append(("error", 0, "bold-bullets",
                      f"{bold_bullets} '**Label**: text' bullets; write prose or plain lists instead"))
    if prose and bullets > prose * 0.6 and bullets > 8:
        found.append(("warn", 0, "bullets",
                      f"{bullets} bullet lines against {prose} prose lines; a document argues in paragraphs"))
    return found


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    errors = 0
    for path in argv:
        for severity, line, rule, detail in sorted(lint(path), key=lambda f: (f[1], f[0])):
            errors += severity == "error"
            where = f"{path}:{line}" if line else path
            print(f"{where}: {severity}: [{rule}] {detail}")
    if errors:
        print(f"\n{errors} error(s). Rewrite those passages before typesetting.")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
