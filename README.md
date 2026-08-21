# qrnix-labs.github.io

QRNix Labs website — product showcase for the QRNix DSP noise-reduction box.

- `index.html` — single-page site: product, controls, modes, features (TK/PP/CLIP), shack setup, specs
- `style.css` — brand stylesheet (colors from the style guide)
- `assets/` — web-ready brand assets copied from the qrnix-labs/brand repo

Photos are not in the repo yet; the HTML contains commented photo-slot
placeholders where they will go.

Deployed via GitHub Pages (branch `main`, root).

## Custom domain: qrnix.com via Cloudflare

The site is live at `https://qrnix-labs.github.io/`. To serve it from
`qrnix.com`, configure GitHub Pages and the Cloudflare DNS zone for
`qrnix.com` as below.

### 1. Tell GitHub Pages about the domain

Repo **Settings → Pages → Custom domain** → enter `qrnix.com` → **Save**.

GitHub records the domain (a `CNAME` file containing `qrnix.com` appears in
the repo automatically) and starts checking DNS. It will show "not configured
yet" until step 2 propagates — that is expected.

### 2. Cloudflare DNS records (zone: `qrnix.com`)

Create these records. **Proxy status must be "DNS only" (grey cloud) for all
of them** — GitHub Pages does not support Cloudflare proxying; orange cloud
breaks certificate issuance and page loading.

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `@` | `185.199.108.153` | DNS only |
| A | `@` | `185.199.109.153` | DNS only |
| A | `@` | `185.199.110.153` | DNS only |
| A | `@` | `185.199.111.153` | DNS only |
| CNAME | `www` | `qrnix-labs.github.io` | DNS only |

The four A records are GitHub's published Pages IPs. The apex uses A records
(not a CNAME) so existing MX/TXT records for email on `qrnix.com` keep
working. Leave any other existing records untouched.

### 3. Verify and enforce HTTPS

1. Propagation takes minutes to a few hours. Check with:
   - `dig qrnix.com` → should return the four IPs above
   - `dig www.qrnix.com` → should return CNAME `qrnix-labs.github.io`
2. Back in **Settings → Pages**, the domain check turns green ("DNS check
   successful").
3. Tick **Enforce HTTPS**. GitHub issues a Let's Encrypt certificate for
   `qrnix.com` (covering `www` too, if the CNAME exists). First issuance can
   take up to 24 h — don't remove the records or the CNAME file while it
   issues.

### Gotchas

- **Orange cloud (proxied) on the Pages records is the #1 breakage** — grey
  cloud (DNS only) only.
- Don't add a second CNAME at the apex alongside the A records; A records are
  the GitHub-documented setup.
- If "Enforce HTTPS" keeps erroring after DNS is correct, wait and re-save —
  certificate issuance lags DNS.
- The `www` CNAME is optional but recommended; without it, `www.qrnix.com`
  does not resolve.
