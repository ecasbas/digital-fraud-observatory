# Digital Fraud Observatory

```text
[ o ]  DIGITAL FRAUD
       OBSERVATORY

Real examples. Learn to spot online fraud.
```

An open library of documented fraud, impersonation and digital deception. Initiated by [desenmascara.me](https://desenmascara.me), open to independent researchers, vendors, educators and individuals.

Start with a public report link and one useful lesson. No code, API key or Desenmascara account is needed. Contributions are reviewed before publication. The collection includes historical website captures and an explicitly fictional reconstruction. It does not claim thousands of existing contributors or established AI involvement in these cases.

## Contribute

The easiest contribution takes about five minutes:

1. Find a public report from a researcher, vendor, regulator, journalist or other attributable source.
2. Open [New example](https://github.com/ecasbas/digital-fraud-observatory/issues/new?template=new-example.yml), paste the report URL, and write one or two sentences explaining what readers should notice or verify.
3. Submit the issue. A maintainer checks the source, privacy, rights and duplication before publishing it as a case.

You can also use the website’s contribution form. [Corrections](https://github.com/ecasbas/digital-fraud-observatory/issues/new?template=correction.yml), translations, code improvements and counterexamples are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the full rules.

## Run locally

Requires Python 3.10 or newer; no packages or application backend.

```sh
python3 scripts/build.py
python3 scripts/check.py
python3 -m http.server 8080 --directory dist
```

Open http://localhost:8080. Edit case records in `content/cases.json`, branding in `site.json`, and presentation in `assets/` or `scripts/build.py`.

## Publish on GitHub Pages

1. Create a public repository and upload this standalone project.
2. Under Settings → Pages, select GitHub Actions as the source.
3. Set repository Actions variable `PAGES_ENABLED` to `true`.
4. Run the Pages workflow on the main branch. It uses the configured Pages URL.
5. For a custom domain, configure it in Pages settings and follow GitHub's DNS instructions.

Set `repository` in `site.json` to the public repository URL to enable contribution links locally. The Pages workflow also supplies the repository URL. The GitHub Pages site is the public deployment. Set a custom domain in Pages settings if the project later moves to one.

## Deployment boundaries

Only `dist/` is published. The source archive contains this project, not Desenmascara's application code. Search and draft preparation run in the browser. Email opens a draft in the visitor's email application; the visitor must send it. GitHub drafts require the visitor to submit an issue. There is no submission server.

## Evidence and rights

Source assessments remain attributed; historical captures do not provide fresh safety verdicts. Original code is MIT licensed. Original editorial text is CC BY 4.0. Third-party screenshots and source content are excluded from those grants. See [NOTICE.md](NOTICE.md) and [CONTENT-LICENSE.md](CONTENT-LICENSE.md).

GitHub documentation: [Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
