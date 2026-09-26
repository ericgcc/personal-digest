"""Generate ``styles/<style>.md`` from the authoritative style modules.

Phase 2b makes the style's rules individually addressable: a stage references the module
that carries the rule it needs instead of asking a Markdown heading to act as an identifier.
The readable ``styles/<style>.md`` document is retained as the style's specification, and it
is *generated* from those modules so the two can never drift apart.

Layout::

    styles/concise/modules/01-style-interface.md
    styles/concise/modules/02-writing-reference-profile.md
    ...
    styles/concise/style.yaml        # ordered manifest: title, intro, modules

Invariants this script enforces:

* ``styles/<style>.md`` is byte-identical to the document the modules were extracted from,
  so the editorial knowledge is preserved exactly and no rule can be lost in the split.
* Every level-2 heading in ``styles/<style>.md`` is owned by exactly one module.
* ``style.yaml`` lists the modules in document order.

Usage::

    python scripts/build_style_docs.py --check     # verify, change nothing (CI / preflight)
    python scripts/build_style_docs.py             # write style.yaml + <style>.md

The generator is deliberately a normal script rather than a package module: it runs at
maintenance time, never during a run, and the runtime reads only the manifest and modules.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLES_DIR = ROOT / "styles"

CANONICAL_STYLES: tuple[str, ...] = ("concise", "curated-discovery", "detailed", "synthesis-max")

_HEADING = re.compile(r"^##\s+(.*?)\s*$")
_ANY_HEADING = re.compile(r"^(#{1,2})\s+(.*?)\s*$", re.MULTILINE)
_H1 = re.compile(r"^#\s+(.*?)\s*$", re.MULTILINE)


def configure_stdio() -> None:
    """The Windows console is cp1252; diagnostics contain typographic characters."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def write_text_lf(path: Path, content: str) -> None:
    """Write UTF-8 with ``\\n`` endings, whatever the platform's default is.

    Python's text mode translates ``\\n`` to ``\\r\\n`` on Windows, which would rewrite every
    style document with different line endings and break the byte-for-byte guarantee this
    generator exists to provide.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def read_text_lf(path: Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def slug(text: str) -> str:
    """A stable, filesystem-safe file name for a heading."""
    text = text.strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "section"


@dataclass(frozen=True)
class Segment:
    title: str
    #: The segment exactly as it appears in the style document: the ``## Heading`` line, the
    #: separator that followed it, and its body. Preserved verbatim so a rebuild cannot
    #: insert or remove a blank line and change the editorial text.
    raw: str

    @property
    def heading(self) -> str:
        return f"## {self.title}"

    @property
    def text(self) -> str:
        """The exact block this module owns."""
        return self.raw.rstrip()


def split_document(text: str) -> tuple[str, list[Segment]]:
    """Split a style document into its verbatim header block and its ``##`` segments.

    The split is lossless: the header block followed by the segment texts joined with
    ``"\\n\\n"`` reproduces ``text.strip()`` exactly. That matters because it is precisely
    the string the pipeline's former section extraction inlined, so the split cannot alter a
    single character of editorial knowledge. The header block (including the ``# Title``
    line and the blank lines that follow it) is preserved verbatim rather than reassembled,
    so no separator convention has to be guessed.
    """
    stripped = text.strip()
    matches = list(_ANY_HEADING.finditer(stripped))
    if not matches:
        return stripped, []
    header = stripped[: matches[0].start()]
    segments: list[Segment] = []
    for index, match in enumerate(matches):
        level, title = match.group(1), match.group(2).strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(stripped)
        if level == "#":
            # A bare ``#`` heading that is not the document's own title is preserved verbatim
            # as part of the header block rather than becoming a module.
            header += stripped[match.start() : end]
            continue
        segments.append(Segment(title=title, raw=stripped[match.start() : end]))
    return header, segments


def document_title(text: str) -> str:
    match = _H1.search(text)
    return match.group(1).strip() if match else ""


def module_filename(index: int, segment: Segment) -> str:
    """The stable module file name for one segment: ``NN-slug.md``."""
    return f"{index:02d}-{slug(segment.title)}.md"


def render_style_doc(header: str, segments: list[Segment]) -> str:
    return header + "\n\n".join(segment.text for segment in segments) + "\n"


@dataclass
class StyleBuild:
    style: str
    source_text: str
    title: str
    header: str
    segments: list[Segment]

    @property
    def document(self) -> str:
        return render_style_doc(self.header, self.segments)


def load_style(style: str) -> StyleBuild:
    path = STYLES_DIR / f"{style}.md"
    text = read_text_lf(path)
    header, segments = split_document(text)
    return StyleBuild(
        style=style,
        source_text=text,
        title=document_title(text) or style,
        header=header,
        segments=segments,
    )


def manifest_text(build: StyleBuild) -> str:
    names = [module_filename(index, segment) for index, segment in enumerate(build.segments, start=1)]
    lines = [
        "# Generated by scripts/build_style_docs.py — do not edit by hand.",
        f"# The ordered modules that compose styles/{build.style}.md.",
        f"id: {build.style}",
        f"title: {build.title}",
        "modules:",
    ]
    for name, segment in zip(names, build.segments):
        lines.append(f"  - file: {name}")
        lines.append(f'    heading: "## {segment.title}"')
    return "\n".join(lines) + "\n"


def plan(build: StyleBuild) -> list[tuple[Path, str]]:
    """Every file this style owns, and its intended content."""
    out_dir = STYLES_DIR / build.style
    files: list[tuple[Path, str]] = [
        (out_dir / "style.yaml", manifest_text(build)),
        (STYLES_DIR / f"{build.style}.md", build.document),
    ]
    for index, segment in enumerate(build.segments, start=1):
        files.append((out_dir / "modules" / module_filename(index, segment), segment.text + "\n"))
    return files


def verify(build: StyleBuild) -> list[str]:
    """Round-trip and ownership checks. Returns a list of problems."""
    problems: list[str] = []
    # The document must round-trip from intro + segments exactly.
    if build.document.strip() != build.source_text.strip():
        problems.append(
            f"styles/{build.style}.md does not round-trip from its modules: "
            f"{len(build.document)} vs {len(build.source_text)} characters"
        )
    # Every level-2 heading must be owned by exactly one module.
    headings = [segment.heading for segment in build.segments]
    if len(headings) != len(set(headings)):
        duplicates = sorted({h for h in headings if headings.count(h) > 1})
        problems.append(f"styles/{build.style}.md declares duplicate headings: {', '.join(duplicates)}")
    # The modules, joined, must reproduce the document's segment region.
    joined = "\n\n".join(segment.text for segment in build.segments)
    if not build.source_text.strip().endswith(joined.strip()):
        problems.append(f"styles/{build.style}.md: joined modules do not reproduce the document tail")
    return problems


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify without writing")
    parser.add_argument("--style", action="append", default=None, help="restrict to one style")
    args = parser.parse_args(argv)

    styles = tuple(args.style) if args.style else CANONICAL_STYLES
    problems: list[str] = []
    planned: list[tuple[Path, str]] = []

    for style in styles:
        build = load_style(style)
        problems.extend(verify(build))
        planned.extend(plan(build))

    # A failing round-trip means the split lost or altered editorial text. Nothing is
    # written in that case, so a broken generator can never overwrite the style documents.
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1

    stale: list[str] = []
    for path, content in planned:
        if args.check:
            existing = read_text_lf(path) if path.exists() else None
            if existing != content:
                stale.append(f"{path.relative_to(ROOT).as_posix()} is out of date; run scripts/build_style_docs.py")
        else:
            write_text_lf(path, content)

    if stale:
        for problem in stale:
            print(f"FAIL {problem}")
        return 1
    verb = "verified" if args.check else "wrote"
    print(f"{verb} {len(planned)} file(s) for {len(styles)} style(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
