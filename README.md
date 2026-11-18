# decimo-docs

The online book of [Decimo](https://github.com/forfudan/decimo), built with
[mdBook](https://rust-lang.github.io/mdBook/). It will be served at
<https://decimo.mojo-lang.com/>.

The book has no text of its own. Every page comes from decimo's user manual,
[`docs/user_manual.md`](https://github.com/forfudan/decimo/blob/main/docs/user_manual.md).
A script cuts the manual into pages at build time. To change a page, edit the
manual in decimo.

## Build and preview

You need Python 3 and mdBook v0.4.40 (`cargo install mdbook --version 0.4.40`).
Without an mdbook on `PATH`, `scripts/build.sh` downloads that release into
`.cache/`.

```sh
bash scripts/build.sh                                   # manual from decimo main
DECIMO_MANUAL=../decimo/docs/user_manual.md bash scripts/build.sh   # a local copy
DECIMO_REF=v0.16.0 bash scripts/build.sh                # a tag or a branch
```

The book is written to `book/`. To preview while you edit the manual:

```sh
python3 scripts/split_manual.py --manual ../decimo/docs/user_manual.md
mdbook serve --open
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
| `.github/workflows/build.yml` | checks the build; asks Cloudflare to rebuild once a day |

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

## The theme

The Ink theme comes from
[yumete-docs](https://github.com/forfudan/yumete-docs). `theme/index.hbs` is
the template of mdBook v0.4.40 with two changes: the theme menu offers only
Ink and Ink dark (mdBook's `light` and `coal`, recoloured by `ink.css`), and
```` ```mojo ```` blocks are coloured as Python, because highlight.js has no
Mojo. The template has to match the mdBook version, so update both together.

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
`CLOUDFLARE_DEPLOY_HOOK` in this repository. The workflow then calls it once a
day. You can also run the workflow by hand.

The build needs the `mdbook:` comments in the manual. A decimo branch without
them stops the split with "no `mdbook: page` comment in the manual".

## Licence

Apache 2.0, as decimo is.
