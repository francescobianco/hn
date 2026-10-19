#!/usr/bin/env python3
"""Read-only Hacker News console: track karma, audit history, find threads worth joining.

Never posts, votes or writes comments. Everything you publish on HN must be written by you.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

API = "https://hacker-news.firebaseio.com/v0"
ALGOLIA = "https://hn.algolia.com/api/v1"
USER = os.environ.get("HN_USER", "francescobianco")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SELF_DOMAINS = ("github.com/francescobianco", "github.com/javanile", "github.com/openapi",
                "yafb.net", "javanile.org", "alterloop.dev", "hookpool.com")


def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def user(name):
    u = get(f"{API}/user/{name}.json")
    if not u:
        sys.exit(f"user {name} not found (or no public activity yet)")
    return u


def item(i):
    return get(f"{API}/item/{i}.json") or {}


def fmt_time(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M")


def cmd_status(args):
    u = user(args.user)
    print(f"user     {u['id']}")
    print(f"karma    {u['karma']}")
    print(f"created  {fmt_time(u['created'])}")
    print(f"items    {len(u.get('submitted', []))}")
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"karma-{args.user}.jsonl")
    history = [json.loads(l) for l in open(path)] if os.path.exists(path) else []
    if history:
        last = history[-1]
        print(f"delta    {u['karma'] - last['karma']:+d} since {fmt_time(last['t'])}")
    with open(path, "a") as f:
        f.write(json.dumps({"t": int(time.time()), "karma": u["karma"]}) + "\n")


def cmd_audit(args):
    u = user(args.user)
    ids = u.get("submitted", [])[: args.limit]
    with ThreadPoolExecutor(16) as ex:
        items = [i for i in ex.map(item, ids) if i]
    stories = [i for i in items if i["type"] == "story"]
    comments = [i for i in items if i["type"] == "comment"]
    dead = [i for i in items if i.get("dead")]
    self_promo = [s for s in stories if any(d in s.get("url", "") for d in SELF_DOMAINS)]
    print(f"stories {len(stories)}  comments {len(comments)}  dead {len(dead)}  self-promo {len(self_promo)}")
    print("domains", Counter(urllib.parse.urlparse(s.get("url", "")).netloc or "text"
                             for s in stories if not s.get("dead")).most_common(8))
    for i in sorted(items, key=lambda x: -x.get("time", 0)):
        text = i.get("title") or (i.get("text") or "").replace("\n", " ")
        flag = "DEAD" if i.get("dead") else "    "
        print(f"{fmt_time(i['time'])} {i['type'][:4]} {flag} s={i.get('score', '-'):<3} {text[:80]}")
    warnings = []
    if stories and len(dead) / len(items) > 0.3:
        warnings.append("Over 30% of your items are dead: your account or domains may be penalized. "
                        "Email hn@ycombinator.com and ask, politely, before posting again.")
    if stories and len(self_promo) / len(stories) > 0.3:
        warnings.append("Over 30% of your stories link to your own projects. Submit other people's work more.")
    if len(comments) < len(stories):
        warnings.append("You post more stories than comments. On HN, karma mostly comes from comments.")
    for w in warnings:
        print("!", w)


def cmd_discover(args):
    """Recent, still-young stories on your topics with few comments: a good place for an early, thoughtful reply."""
    since = int(time.time()) - args.hours * 3600
    seen = {}
    for topic in args.topics:
        q = urllib.parse.urlencode({"query": topic, "tags": "story",
                                    "numericFilters": f"created_at_i>{since},points>={args.min_points}"})
        for h in get(f"{ALGOLIA}/search_by_date?{q}")["hits"]:
            seen.setdefault(h["objectID"], h)
    hits = sorted(seen.values(), key=lambda h: (h.get("num_comments") or 0) - (h.get("points") or 0))
    for h in hits[: args.limit]:
        age = (time.time() - h["created_at_i"]) / 3600
        print(f"{h['points']:>4}p {h.get('num_comments') or 0:>3}c {age:4.1f}h  {h['title'][:70]}")
        print(f"{'':16}https://news.ycombinator.com/item?id={h['objectID']}")


def cmd_replies(args):
    """Recent replies to your comments and stories, so you can keep conversations going."""
    q = urllib.parse.urlencode({"tags": f"comment,author_{args.user}", "hitsPerPage": args.limit})
    mine = get(f"{ALGOLIA}/search_by_date?{q}")["hits"]
    for c in mine:
        kids = item(int(c["objectID"])).get("kids", [])
        if kids:
            print(f"{fmt_time(c['created_at_i'])} {len(kids)} replies  https://news.ycombinator.com/item?id={c['objectID']}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--user", default=USER)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="karma now and delta since last run").set_defaults(fn=cmd_status)
    a = sub.add_parser("audit", help="review your history and common problems")
    a.add_argument("--limit", type=int, default=200)
    a.set_defaults(fn=cmd_audit)
    d = sub.add_parser("discover", help="young threads on your topics")
    d.add_argument("topics", nargs="*", default=["linux", "open source", "bash", "compiler", "symbolic ai", "devops"])
    d.add_argument("--hours", type=int, default=6)
    d.add_argument("--min-points", type=int, default=5)
    d.add_argument("--limit", type=int, default=20)
    d.set_defaults(fn=cmd_discover)
    r = sub.add_parser("replies", help="your recent comments that got answers")
    r.add_argument("--limit", type=int, default=30)
    r.set_defaults(fn=cmd_replies)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
