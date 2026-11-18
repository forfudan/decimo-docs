#!/usr/bin/env bash
# Builds the book into book/.
#
#   bash scripts/build.sh                                   # manual from decimo main
#   DECIMO_REF=v0.16.0 bash scripts/build.sh                # from a tag or a branch
#   DECIMO_MANUAL=../decimo/docs/user_manual.md bash scripts/build.sh   # a local copy
#
# It splits the manual into src/ (scripts/split_manual.py), then runs
# `mdbook build`. It uses the mdbook on PATH. On a machine without one, such
# as the Cloudflare build image, it downloads the pinned release once into
# .cache/. Any warning from mdbook fails the build, so a broken page cannot
# reach the site.
set -euo pipefail

# A relative DECIMO_MANUAL is read from where you are, not from the book.
if [[ -n ${DECIMO_MANUAL:-} ]]; then
    DECIMO_MANUAL=$(cd "$(dirname "$DECIMO_MANUAL")" && pwd)/$(basename "$DECIMO_MANUAL")
fi
cd "$(dirname "$0")/.."

# The release that theme/index.hbs was copied from. The template has to
# match the mdbook that renders it, so change both together.
MDBOOK_VERSION=v0.4.40

if [[ -n ${DECIMO_MANUAL:-} ]]; then
    python3 scripts/split_manual.py --manual "$DECIMO_MANUAL"
else
    python3 scripts/split_manual.py --ref "${DECIMO_REF:-main}"
fi

if command -v mdbook > /dev/null; then
    MDBOOK=mdbook
    have=$(mdbook --version | awk '{print $2}')
    if [[ $have != "$MDBOOK_VERSION" ]]; then
        echo "build.sh: mdbook on PATH is $have; the theme is made for $MDBOOK_VERSION" >&2
    fi
else
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64) target=x86_64-unknown-linux-gnu ;;
        Linux-aarch64) target=aarch64-unknown-linux-musl ;;
        Darwin-*) target=x86_64-apple-darwin ;;
        *)
            echo "build.sh: no mdbook release for this machine; install mdbook $MDBOOK_VERSION" >&2
            exit 1
            ;;
    esac
    MDBOOK=.cache/mdbook-$MDBOOK_VERSION/mdbook
    if [[ ! -x $MDBOOK ]]; then
        mkdir -p "$(dirname "$MDBOOK")"
        url=https://github.com/rust-lang/mdBook/releases/download/$MDBOOK_VERSION/mdbook-$MDBOOK_VERSION-$target.tar.gz
        echo "build.sh: downloading $url"
        curl -sSfL "$url" | tar -xz -C "$(dirname "$MDBOOK")"
    fi
fi

mkdir -p .cache
"$MDBOOK" build 2>&1 | tee .cache/build.log
if grep -E '\[(WARN|ERROR)\]' .cache/build.log > /dev/null; then
    echo "build.sh: mdbook printed a warning; see above" >&2
    exit 1
fi
echo "build.sh: the book is in book/"
