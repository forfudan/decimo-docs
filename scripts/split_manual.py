#!/usr/bin/env python3
"""Splits decimo's user manual into the pages of this book.

The manual, `docs/user_manual.md` in the decimo repository, is the only
source. This script reads it, cuts it into pages at its `mdbook:` comments,
writes the pages and `SUMMARY.md` into `src/`, and fixes the links. `src/` is
written from scratch on every run, so it is not committed.

Usage:
    python3 scripts/split_manual.py                     # fetch decimo main
    python3 scripts/split_manual.py --ref v0.16.0       # fetch a tag or branch
    python3 scripts/split_manual.py --manual ../decimo/docs/user_manual.md

The comments in the manual (GitHub does not show them):

    <!-- mdbook: page file="bigint/index.md" title="Part I" -->
        A new page starts here and runs to the next `page` comment. `file` is
        the page's path under `src/`. `title` is the name in the sidebar; it
        is optional and defaults to the page's first heading. A page
        `a/b.md` is listed under `a/index.md` when that page exists.
    <!-- mdbook: part title="Appendices" -->
        A part title in the sidebar, above the next page.
    <!-- mdbook: skip --> ... <!-- mdbook: end skip -->
        Lines between the two are left out of the book (the hand-written table
        of contents: the sidebar does that job here).

On each page the headings move up so that the first one is `#`, the
`<!-- omit from toc -->` markers are removed, and a link to `#anchor` that
now lives on another page is pointed at that page. A relative link to a file
in the decimo repository is pointed at GitHub. A link to an anchor that does
not exist stops the script, so a broken link cannot reach the site.

Only the Python standard library is used.
"""

import argparse
import os
import posixpath
import re
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "forfudan/decimo"
MANUAL = "docs/user_manual.md"

MARKER = re.compile(r"^\s*<!--\s*mdbook:\s*(.*?)\s*-->\s*$")
ATTR = re.compile(r'(\w+)="([^"]*)"')
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
COMMENT = re.compile(r"<!--.*?-->", re.S)
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
LINK = re.compile(r'(!?)\[([^\]]*)\]\(([^)\s]+)((?:\s+"[^"]*")?)\)')
LINK_DEF = re.compile(r"^(\s{0,3}\[[^\]]+\]:\s*)(\S+)(.*)$")


class SplitError(Exception):
    pass


def read_manual(args):
    if args.manual:
        with open(args.manual, encoding="utf-8") as f:
            return f.read(), args.manual
    url = "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, args.ref, MANUAL)
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8"), url


def fenced(lines):
    """Yields `(line, inside a code block)` for each line."""
    fence = None
    for line in lines:
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            yield line, True
        elif fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                if line.strip() == m.group(1):
                    fence = None
            yield line, True
        else:
            yield line, False


def plain(text):
    """The words of a heading, as both GitHub and mdBook see them."""
    text = COMMENT.sub("", text)
    out = []
    pos = 0
    for m in CODE_SPAN.finditer(text):
        out.append(_plain_prose(text[pos : m.start()]))
        out.append(m.group(2).strip())
        pos = m.end()
    out.append(_plain_prose(text[pos:]))
    return "".join(out).strip()


def _plain_prose(text):
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]*>", "", text)
    text = text.replace("*", "")
    return re.sub(r"\\(.)", r"\1", text)


def github_slug(text):
    """The anchor GitHub gives a heading (github-slugger)."""
    return re.sub(r"[^\w\- ]", "", plain(text).lower()).replace(" ", "-")


def mdbook_slug(text):
    """The anchor mdBook 0.4 gives a heading (`normalize_id`)."""
    out = []
    for ch in plain(text):
        if ch.isalnum() or ch in "_-":
            out.append(ch.lower() if ch.isascii() else ch)
        elif ch.isspace():
            out.append("-")
    return "".join(out)


def unique(slug, seen):
    n = seen.get(slug, 0)
    seen[slug] = n + 1
    return slug if n == 0 else "%s-%d" % (slug, n)


def parse(text):
    """Cuts the manual into pages. Each page keeps its lines in order."""
    pages = []
    part = None
    skipping = False
    preamble = []
    github_seen = {}
    for number, (line, code) in enumerate(fenced(text.split("\n")), 1):
        m = None if code else MARKER.match(line)
        if m:
            command = m.group(1)
            attrs = dict(ATTR.findall(command))
            word = ATTR.sub("", command).strip()
            if word == "skip":
                if skipping:
                    raise SplitError("line %d: skip inside skip" % number)
                skipping = True
            elif word == "end skip":
                if not skipping:
                    raise SplitError("line %d: end skip without skip" % number)
                skipping = False
            elif word == "part":
                part = attrs.get("title") or _fail(number, "part needs a title")
            elif word == "page":
                if skipping:
                    raise SplitError("line %d: page inside skip" % number)
                pages.append(
                    {
                        "file": attrs.get("file") or _fail(number, "page needs a file"),
                        "title": attrs.get("title"),
                        "part": part,
                        "line": number,
                        "lines": [],
                    }
                )
                part = None
            else:
                raise SplitError("line %d: unknown mdbook comment %r" % (number, word))
            continue
        # Every heading gets GitHub's anchor, skipped or not, since GitHub
        # numbers repeated anchors over the whole file.
        h = None if code else HEADING.match(line)
        anchor = unique(github_slug(h.group(2)), github_seen) if h else None
        if skipping:
            continue
        if not pages:
            preamble.append(line)
            continue
        pages[-1]["lines"].append((line, code, anchor))
    if skipping:
        raise SplitError("a skip is never ended")
    if not pages:
        raise SplitError("no `mdbook: page` comment in the manual")
    if COMMENT.sub("", "\n".join(preamble)).strip():
        raise SplitError("text before the first page comment would be lost")
    return pages


def _fail(number, message):
    raise SplitError("line %d: %s" % (number, message))


def check_files(pages):
    seen = set()
    for page in pages:
        f = page["file"]
        if (
            not f.endswith(".md")
            or f.startswith("/")
            or ".." in f.split("/")
            or f == "SUMMARY.md"
        ):
            raise SplitError("line %d: bad file name %r" % (page["line"], f))
        if f in seen:
            raise SplitError("line %d: %r is used twice" % (page["line"], f))
        seen.add(f)


def shape(page):
    """Moves the headings up and gives each its mdBook anchor."""
    levels = [
        len(HEADING.match(l).group(1))
        for l, code, _ in page["lines"]
        if not code and HEADING.match(l)
    ]
    if not levels:
        raise SplitError("line %d: the page has no heading" % page["line"])
    shift = min(levels) - 1
    seen = {}
    out = []
    page["anchors"] = {}
    for line, code, anchor in page["lines"]:
        h = None if code else HEADING.match(line)
        if h:
            words = COMMENT.sub("", h.group(2)).strip()
            line = "#" * (len(h.group(1)) - shift) + " " + words
            if "heading" not in page:
                page["heading"] = words
                page["first_anchor"] = anchor
            page["anchors"][anchor] = unique(mdbook_slug(words), seen)
        out.append((line, code))
    page["lines"] = out
    if not page["title"]:
        page["title"] = plain(page["heading"])


def relink(page, where, ref):
    """Points each link at the page where its target now lives."""

    def target(url, image):
        if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I) or url.startswith("/"):
            return url
        if url.startswith("#"):
            anchor = url[1:]
            if anchor not in where:
                raise SplitError(
                    "%s: the link to #%s goes nowhere" % (page["file"], anchor)
                )
            file, slug, first = where[anchor]
            if file == page["file"]:
                return "#" + slug
            rel = posixpath.relpath(file, posixpath.dirname(page["file"]) or ".")
            return rel if first else rel + "#" + slug
        path, _, frag = url.partition("#")
        path = posixpath.normpath(posixpath.join(posixpath.dirname(MANUAL), path))
        if image:
            return "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, ref, path)
        out = "https://github.com/%s/blob/%s/%s" % (REPO, ref, path)
        return out + ("#" + frag if frag else "")

    def links(text):
        return LINK.sub(
            lambda m: "%s[%s](%s%s)"
            % (m.group(1), m.group(2), target(m.group(3), m.group(1)), m.group(4)),
            text,
        )

    def one_line(line):
        d = LINK_DEF.match(line)
        if d:
            return d.group(1) + target(d.group(2), False) + d.group(3)
        # Code spans are left alone: `x[i](#y)` in code is not a link.
        parts = []
        pos = 0
        for m in CODE_SPAN.finditer(line):
            parts.append(links(line[pos : m.start()]))
            parts.append(m.group(0))
            pos = m.end()
        parts.append(links(line[pos:]))
        return "".join(parts)

    page["lines"] = [(l if code else one_line(l), code) for l, code in page["lines"]]


def parent_of(file, files):
    parts = file.split("/")
    if parts[-1] == "index.md":
        parts = parts[:-1]
    if len(parts) <= 1:
        return None
    candidate = "/".join(parts[:-1] + ["index.md"])
    return candidate if candidate in files and candidate != file else None


def summary(pages):
    files = {p["file"] for p in pages}
    depth = {}
    lines = ["# Summary", ""]
    first, rest = pages[0], pages[1:]
    lines += ["[%s](%s)" % (_escape(first["title"]), first["file"]), ""]
    for page in rest:
        parent = parent_of(page["file"], files)
        if parent is not None and parent not in depth:
            raise SplitError("%s comes before its parent %s" % (page["file"], parent))
        depth[page["file"]] = 0 if parent is None else depth[parent] + 1
        if page["part"]:
            if depth[page["file"]]:
                raise SplitError("the part above %s must be on a top page" % page["file"])
            lines += ["", "# " + page["part"], ""]
        lines.append(
            "%s- [%s](%s)"
            % ("  " * depth[page["file"]], _escape(page["title"]), page["file"])
        )
    return "\n".join(lines) + "\n"


def _escape(title):
    return title.replace("[", "\\[").replace("]", "\\]")


HEADER = (
    "<!-- Written by scripts/split_manual.py from docs/user_manual.md in %s.\n"
    "     Edit the manual there, not this file. -->\n\n"
)


def write(pages, out):
    if os.path.isdir(out):
        for base, _, names in os.walk(out):
            for name in names:
                if not name.endswith(".md"):
                    raise SplitError(
                        "%s holds %s, which this script did not write; not removing it"
                        % (out, os.path.join(base, name))
                    )
        shutil.rmtree(out)
    for page in pages:
        lines = [l for l, _ in page["lines"]]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        path = os.path.join(out, *page["file"].split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(HEADER % REPO + "\n".join(lines) + "\n")
    with open(os.path.join(out, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write(summary(pages))


def split(text, out, ref):
    pages = parse(text)
    check_files(pages)
    for page in pages:
        shape(page)
    where = {}
    for page in pages:
        for anchor, slug in page["anchors"].items():
            where[anchor] = (page["file"], slug, anchor == page["first_anchor"])
    for page in pages:
        relink(page, where, ref)
    write(pages, out)
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manual", help="a local copy of user_manual.md")
    parser.add_argument(
        "--ref",
        default=os.environ.get("DECIMO_REF", "main"),
        help="the decimo branch or tag to fetch, and to link to (default: main)",
    )
    parser.add_argument(
        "--out", default=os.path.join(ROOT, "src"), help="where to write the pages"
    )
    args = parser.parse_args()
    try:
        text, source = read_manual(args)
        pages = split(text, args.out, args.ref)
    except (SplitError, OSError) as e:
        print("split_manual: %s" % e, file=sys.stderr)
        return 1
    print("split_manual: %d pages from %s" % (len(pages), source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
