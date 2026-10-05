#!/usr/bin/env python3
"""Link isolation check for per-app legal pages.

Scans every app page (/<lang>/privacy/<slug>.html and /<lang>/support/<slug>.html),
infers the app from the slug in the path, extracts every href / src / mailto, and
fails (exit 1) on anything outside the four allowed categories:

  1. the same app's language switch        (/en|/zh-hant)/(privacy|support)/<slug>
  2. the same app's privacy <-> support    (same lang, same slug)
  3. mailto: the app's own support address (see APP_EMAILS)
  4. shared assets (/assets/...), apple.com domains, reportaproblem.apple.com,
     plus the third-party policy hosts in THIRD_PARTY_POLICY_HOSTS (links to an
     SDK vendor's own privacy documentation are not cross-app leaks)

Anything else is a violation: other app slugs, the core language-learning pages
(/en/privacy.html, terms, licenses), the site root / index.html, an email that
belongs to a different app, or a header icon wrapped in <a>.

Usage:  python3 scripts/check-links.py          (run from the repo root; exit 0 = clean)
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("en", "zh-hant")
KINDS = ("privacy", "support")

# slug -> the only mailto allowed on that app's pages
APP_EMAILS = {
    "dicecrawl": "lingjihelp+dc_support@gmail.com",
    "metawipe": "lingjihelp+metawipe_support@gmail.com",
    "resin-calculator": "lingjihelp+resin_support@gmail.com",
    "goblinocracy": "lingjihelp+goblinocracy_support@gmail.com",
}
APPLE_HOSTS = {"apple.com", "www.apple.com", "reportaproblem.apple.com", "support.apple.com"}
THIRD_PARTY_POLICY_HOSTS = {"policies.google.com", "support.google.com"}

PAGE_RE = re.compile(r"^(?P<lang>en|zh-hant)/(?P<kind>privacy|support)/(?P<slug>[a-z0-9-]+)\.html$")
ATTR_RE = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"']*)["']""", re.I)
ICON_IN_ANCHOR_RE = re.compile(r"<a\b[^>]*>(?:(?!</a>).)*?<img\b[^>]*lj-header-logo", re.I | re.S)


def app_pages():
    for lang in LANGS:
        for kind in KINDS:
            for p in sorted((ROOT / lang / kind).glob("*.html")):
                rel = p.relative_to(ROOT).as_posix()
                m = PAGE_RE.match(rel)
                if m:
                    yield p, rel, m.group("lang"), m.group("kind"), m.group("slug")


def check_url(url, lang, kind, slug):
    """Return None if allowed, else a short reason."""
    u = url.strip()
    if u.startswith("#"):
        return None
    if u.lower().startswith("mailto:"):
        addr = u[7:].split("?")[0].strip().lower()
        want = APP_EMAILS.get(slug)
        if want is None:
            return f"unknown app slug '{slug}' (add it to APP_EMAILS)"
        return None if addr == want.lower() else f"mailto for a different app ({addr}, expected {want})"
    parsed = urlparse(u)
    if parsed.scheme in ("http", "https"):
        host = (parsed.hostname or "").lower()
        if host in APPLE_HOSTS or host.endswith(".apple.com"):
            return None
        if host in THIRD_PARTY_POLICY_HOSTS:
            return None
        return f"external host not allowed ({host})"
    if parsed.scheme:
        return f"scheme not allowed ({parsed.scheme})"
    path = parsed.path
    if path.startswith("/assets/"):
        return None
    if not path.startswith("/"):
        return f"relative link not allowed ({path})"
    # same-app privacy/support pages, either language, with or without .html
    m = re.fullmatch(r"/(en|zh-hant)/(privacy|support)/([a-z0-9-]+)(?:\.html)?/?", path)
    if m:
        return None if m.group(3) == slug else f"links to another app's page ({path})"
    if path in ("/", "/index.html") or re.fullmatch(r"/[a-z-]+/(privacy|terms|licenses)(?:\.html)?/?", path):
        return f"links to a core/site page ({path})"
    return f"path not allowed ({path})"


def main():
    pages = list(app_pages())
    violations = []
    for p, rel, lang, kind, slug in pages:
        html = p.read_text(encoding="utf-8")
        if ICON_IN_ANCHOR_RE.search(html):
            violations.append((rel, "<img class=lj-header-logo> is wrapped in <a>", ""))
        for url in ATTR_RE.findall(html):
            why = check_url(url, lang, kind, slug)
            if why:
                violations.append((rel, why, url))
    print(f"check-links: scanned {len(pages)} app pages")
    for rel, why, url in violations:
        print(f"  VIOLATION {rel}: {why}" + (f"  [{url}]" if url else ""))
    if violations:
        print(f"check-links: {len(violations)} violation(s)")
        return 1
    print("check-links: 0 violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
