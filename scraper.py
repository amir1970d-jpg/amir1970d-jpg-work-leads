import json, re, datetime, hashlib, os
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (compatible; work-leads-bot/1.0)", "Accept-Language": "fa,en;q=0.8"}
TODAY = datetime.date.today().isoformat()


def norm(s):
    s = (s or "").replace("ي", "ی").replace("ك", "ک").lower()
    return re.sub(r"[\s\u200c\u200e\u200f]+", "", s)


def has_any(text, words):
    t = norm(text)
    return any(norm(w) in t for w in words)


def get(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def item(title, url, source):
    title = re.sub(r"\s+", " ", title).strip()[:160]
    return {"id": hashlib.md5(url.encode()).hexdigest()[:12], "title": title,
            "url": url, "source": source, "found": TODAY}


def scan_links(soup, base, cfg, source, need_demand):
    out = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        if len(title) < 8:
            continue
        ctx = title + " " + (a.parent.get_text(" ", strip=True)[:300] if a.parent else "")
        if not has_any(ctx, cfg["skills"]):
            continue
        if need_demand and not has_any(ctx, cfg["demand"]):
            continue
        out.append(item(title, urljoin(base, a["href"]), source))
    return out


def run_source(src, cfg):
    t = src["type"]
    if t == "search":
        res = []
        for kw in cfg["search_terms"]:
            soup = get(src["url"].format(kw=quote(kw)))
            res += scan_links(soup, src["url"], cfg, src["name"], need_demand=False)
        return res
    if t == "links":
        return scan_links(get(src["url"]), src["url"], cfg, src["name"], need_demand=True)
    if t == "telegram":
        soup = get("https://t.me/s/" + src["channel"])
        res = []
        for m in soup.select(".tgme_widget_message"):
            txt_el = m.select_one(".tgme_widget_message_text")
            link_el = m.select_one("a.tgme_widget_message_date")
            if not txt_el or not link_el:
                continue
            txt = txt_el.get_text(" ", strip=True)
            if has_any(txt, cfg["skills"]) and has_any(txt, cfg["demand"]):
                res.append(item(txt, link_el["href"], src["name"]))
        return res
    raise ValueError("unknown type " + t)


def main():
    cfg = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
    path = os.path.join(HERE, "leads.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"items": []}
    items = {i["id"]: i for i in old.get("items", [])}
    status = []
    for src in cfg["sources"]:
        if src.get("disabled"):
            continue
        try:
            found = run_source(src, cfg)
            new = 0
            for it in found:
                if it["id"] not in items:
                    items[it["id"]] = it
                    new += 1
            status.append({"name": src["name"], "ok": True, "found": len(found), "new": new})
        except Exception as e:
            status.append({"name": src["name"], "ok": False, "error": str(e)[:200]})
    cutoff = (datetime.date.today() - datetime.timedelta(days=cfg.get("keep_days", 45))).isoformat()
    kept = sorted((i for i in items.values() if i["found"] >= cutoff), key=lambda i: i["found"], reverse=True)
    json.dump({"updated": TODAY, "status": status, "items": kept}, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for s in status:
        print(s)


if __name__ == "__main__":
    main()
