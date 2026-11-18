# decimo-docs

The online book of [Decimo](https://github.com/forfudan/decimo), built with
[mdBook](https://rust-lang.github.io/mdBook/). It will be served at
<https://decimo.mojo-lang.com/>.

The book has no text of its own. Every page comes from decimo's user manual,
[`docs/user_manual.md`](https://github.com/forfudan/decimo/blob/main/docs/user_manual.md).
A script cuts the manual into pages at build time. To change a page, edit the
manual in decimo.

## Build and preview

You need Python 3. `scripts/build.sh` uses mdBook v0.5.4: the `mdbook` on
`PATH` if it is that version, or else the release it downloads once into
`.cache/`.

```sh
bash scripts/build.sh                                   # manual from DECIMO_REF (main)
DECIMO_MANUAL=../decimo/docs/user_manual.md bash scripts/build.sh   # a local copy
DECIMO_REF=v0.17.0 bash scripts/build.sh                # another tag or branch
```

The book is written to `book/`. To preview while you edit the manual (after
one `build.sh`, which fetches mdbook):

```sh
python3 scripts/split_manual.py --manual ../decimo/docs/user_manual.md
.cache/mdbook-v0.5.4/mdbook serve --open      # or `mdbook serve` if yours is v0.5.4
```

Run the split again after each change to the manual. `mdbook serve` then
reloads the page.

## Where things are

| Path | What it is |
| --- | --- |
| `book.toml` | the mdBook settings |
| `scripts/split_manual.py` | cuts the manual into `src/` and writes `src/SUMMARY.md` |
| `scripts/build.sh` | runs the split, then `mdbook build`; fails on any mdbook warning |
| `theme/index.hbs` | mdBook's own template with two changes (see below) |
| `theme/ink.css` | the Ink colours, light and dark |
| `theme/custom.css` | the reading width and the line height |
| `src/` | the pages; written by the script, not committed |
| `.github/workflows/build.yml` | checks that the book builds |

## How the manual is cut

The manual carries HTML comments that GitHub does not show:

```md
<!-- mdbook: page file="bigint/construction.md" -->
### Construction
```

- `page` starts a new page. The page runs to the next `page` comment. `file`
  is the page's path under `src/`. `title="..."` sets the name in the sidebar;
  without it, the name is the first heading of the page. A page `a/b.md` is
  listed under `a/index.md`.
- `<!-- mdbook: part title="Appendices" -->` puts a part title in the sidebar,
  above the next page.
- `<!-- mdbook: skip -->` and `<!-- mdbook: end skip -->` leave the lines
  between them out of the book. The manual's own table of contents is left
  out this way, because the sidebar does the same job.

On each page, the script moves the headings up so that the first one is `#`,
and removes the `<!-- omit from toc -->` markers. A link to `#anchor` in the
manual is pointed at the page that now holds that heading. A relative link to
a file in decimo is pointed at GitHub. A link to an anchor that does not exist
stops the build.

A new section in the manual that has no `page` comment becomes part of the
page above it. To give it a page of its own, add a `page` comment above its
heading.

## Which version of the manual

The site shows the manual of the decimo branch or tag in `DECIMO_REF`, set on
one line near the top of `scripts/build.sh`. It is `main` for now. It should
become the latest release tag once a release has the `mdbook:` comments in its
manual. That one line is the whole change (and decimo's
`rebuild_book.yaml` should then run on a release; see its comments).

## The theme

The Ink theme comes from
[yumete-docs](https://github.com/forfudan/yumete-docs): the colours in
`theme/ink.css` and the reading width in `theme/custom.css`.

`theme/index.hbs` is the default template of mdBook v0.5.4 with two changes,
each marked with a `decimo-docs edit` comment:

1. The theme menu offers only Ink and Ink dark. They are mdBook's `light` and
   `coal` themes, recoloured by `ink.css`.
2. ```` ```mojo ```` blocks are coloured as Python, because highlight.js has no
   Mojo.

The template has to match the mdBook version. To move to a new mdBook:

```sh
mdbook init --theme /tmp/fresh        # with the new mdbook; answer the questions
diff /tmp/fresh/theme/index.hbs theme/index.hbs   # shows only the two edits
```

Copy the new `index.hbs` over ours, apply the two edits again, change
`MDBOOK_VERSION` in `scripts/build.sh`, and check that `ink.css` covers any
new colour variables in the new `css/variables.css`.

## Deploying to Cloudflare Pages

Cloudflare builds the site from this repository and serves it.

1. Cloudflare dashboard → **Workers & Pages** → **Create** → **Pages** →
   **Connect to Git**. Pick this repository.
2. Build settings:
   - Framework preset: **None**
   - Build command: `bash scripts/build.sh`
   - Build output directory: `book`
   - Root directory: `/`
   - Optional variable `DECIMO_REF`: the decimo branch or tag to build from
     (default `main`).
3. Save and deploy. Each push to `main` rebuilds the site. Other branches get
   preview URLs.
4. **Custom domains** → **Set up a domain** → `decimo.mojo-lang.com`. If the
   DNS of `mojo-lang.com` is on Cloudflare, it adds the record itself.
   Otherwise, add the `CNAME` record that Cloudflare shows.

A change to the manual in decimo does not push anything here. To bring it to
the site, create a deploy hook in the Pages project (**Settings** →
**Builds & deployments** → **Deploy hooks**) and save its URL as the secret
`CLOUDFLARE_DEPLOY_HOOK` in the **decimo** repository. decimo's workflow
`.github/workflows/rebuild_book.yaml` calls it when `docs/user_manual.md`
changes on `main`. A **Retry deployment** in the Cloudflare dashboard does the
same by hand.

The build needs the `mdbook:` comments in the manual. A decimo branch without
them stops the split with "no `mdbook: page` comment in the manual".

## Licence

Apache 2.0, as decimo is.
