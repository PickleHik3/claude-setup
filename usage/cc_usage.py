"""cc-usage: tokens, cost, time and outcome of every Claude Code agent, across sessions.

`collect` scans the transcripts into SQLite, `outcome` records whether a worker's task worked,
`report` shows both. Python 3 standard library only, no network.

What it relies on, checked on Claude Code 2.1.330 (2026-11-22). None of it is documented, so
`collect` validates the fields and warns when one goes missing instead of undercounting silently:
- <config>/projects/<encoded dir>/<session-id>.jsonl is the main transcript, one JSON object per
  line; assistant lines carry message.model, message.usage (input_tokens, output_tokens,
  cache_read_input_tokens, cache_creation_input_tokens, cache_creation.ephemeral_{5m,1h}_input_tokens,
  speed), timestamp, requestId, effort, sessionId, cwd, version, isSidechain.
- <session-id>/subagents/agent-<id>.jsonl is a subagent's transcript, agent-<id>.meta.json holds
  agentType, model, description, parentAgentId, spawnDepth.
- One API response may be split over several lines with the same requestId; usage is counted once.
Cost is the API list-price equivalent from prices.json, not a bill.
"""
import argparse, glob, json, os, re, sqlite3, statistics, sys, time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
GAP_CAP = 300  # seconds of a gap between lines that still counts as active time
BUCKETS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
NEEDED = (("message.model", lambda d, m, u: m.get("model")),
          ("message.usage", lambda d, m, u: u or None),
          ("message.usage.input_tokens", lambda d, m, u: u.get("input_tokens")),
          ("message.usage.output_tokens", lambda d, m, u: u.get("output_tokens")),
          ("message.usage.cache_read_input_tokens", lambda d, m, u: u.get("cache_read_input_tokens")),
          ("message.usage.cache_creation_input_tokens", lambda d, m, u: u.get("cache_creation_input_tokens")),
          ("timestamp", lambda d, m, u: d.get("timestamp")),
          ("requestId or message.id", lambda d, m, u: d.get("requestId") or m.get("id")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, size INT, mtime INT, offset INT);
CREATE TABLE IF NOT EXISTS requests(
  key TEXT PRIMARY KEY, session TEXT, agent_id TEXT, ts TEXT, epoch REAL, model TEXT, effort TEXT,
  input INT, cache_write_5m INT, cache_write_1h INT, cache_read INT, output INT, thinking INT,
  cost REAL, fast INT);
CREATE INDEX IF NOT EXISTS req_agent ON requests(session, agent_id);
CREATE TABLE IF NOT EXISTS agents(
  session TEXT, agent_id TEXT, project TEXT, role TEXT, parent_agent_id TEXT, spawn_depth INT,
  description TEXT, model TEXT, effort TEXT, started_at TEXT, ended_at TEXT, wall_s REAL,
  active_s REAL, requests INT, tool_calls INT, input INT, cache_write_5m INT, cache_write_1h INT,
  cache_read INT, output INT, thinking INT, cost REAL, unpriced INT, fast INT, version TEXT,
  last_epoch REAL, first_epoch REAL, PRIMARY KEY(session, agent_id));
CREATE TABLE IF NOT EXISTS outcomes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, outcome TEXT, kind TEXT, missed TEXT,
  retry_of TEXT, pair TEXT, note TEXT, ts TEXT);
"""


def config_dir():
    return (os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")).rstrip("/")


def db_path():
    return os.environ.get("CC_USAGE_DB") or os.path.expanduser("~/.claude-memory/claude-setup/usage.db")


_OPEN = []


def connect():
    p = db_path()
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _OPEN.append(conn)
    return conn


# ---------------------------------------------------------------- prices

def load_prices():
    p = os.environ.get("CC_USAGE_PRICES") or os.path.join(HERE, "prices.json")
    with open(p) as f:
        return json.load(f)


def price_for(prices, model):
    models = prices["models"]
    if model in models:
        return models[model]
    stripped = re.sub(r"-\d{8}$", "", model or "")
    return models.get(stripped)


def cost_of(prices, model, tok, fast):
    """Dollars for one request, or None for an unknown model. tok has the five buckets."""
    p = price_for(prices, model)
    if p is None:
        return None
    rates = p
    lc = p.get("long_context")
    if lc:
        prompt = tok["input"] + tok["cache_read"] + tok["cache_write_5m"] + tok["cache_write_1h"]
        if prompt > lc["threshold"]:
            rates = lc
    total = sum(tok[b] * rates[b] for b in BUCKETS) / 1e6
    if fast:
        total *= p.get("fast_multiplier", 1)
    return total


# ---------------------------------------------------------------- collect

def epoch_of(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def iso_of(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def usage_tokens(u):
    cc = u.get("cache_creation") or {}
    total = u.get("cache_creation_input_tokens") or 0
    w1 = cc.get("ephemeral_1h_input_tokens") or 0
    w5 = cc.get("ephemeral_5m_input_tokens") or 0
    if w1 + w5 < total:
        w5 += total - (w1 + w5)  # no split given: bill the rest as 5 minute writes
    return {"input": u.get("input_tokens") or 0, "cache_write_5m": w5, "cache_write_1h": w1,
            "cache_read": u.get("cache_read_input_tokens") or 0,
            "output": u.get("output_tokens") or 0,
            "thinking": (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0}


class Collector:
    def __init__(self, conn, prices):
        self.conn, self.prices = conn, prices
        self.warned = {}      # warning text -> True
        self.missing = {}     # field -> version
        self.unknown = set()
        self.touched = set()
        self.lines = 0

    def warn(self, text):
        if text not in self.warned:
            self.warned[text] = True
            print("cc-usage: warning: " + text, file=sys.stderr)

    def scan(self, cfg):
        files = []
        for proj in sorted(glob.glob(os.path.join(cfg, "projects", "*"))):
            for p in glob.glob(os.path.join(proj, "*.jsonl")):
                sid = os.path.basename(p)[:-6]
                files.append((p, proj, sid, "main"))
            for p in glob.glob(os.path.join(proj, "*", "subagents", "**", "agent-*.jsonl"), recursive=True):
                sid = os.path.relpath(p, proj).split(os.sep)[0]
                files.append((p, proj, sid, os.path.basename(p)[6:-6]))
        for p, proj, sid, aid in files:
            try:
                self.file(p, proj, sid, aid)
            except Exception as e:  # one bad file must not stop the scan
                self.warn("%s: %s: %s" % (os.path.basename(p), type(e).__name__, e))
        self.finish()
        for field, ver in self.missing.items():
            self.warn("transcript field missing: %s (Claude Code version %s); usage may be undercounted"
                      % (field, ver))

    def agent_row(self, sid, aid, proj):
        r = self.conn.execute("SELECT * FROM agents WHERE session=? AND agent_id=?", (sid, aid)).fetchone()
        if r:
            return dict(r)
        return {"session": sid, "agent_id": aid, "project": os.path.basename(proj), "role": "main" if aid == "main" else "unknown",
                "parent_agent_id": None, "spawn_depth": 0 if aid == "main" else None, "description": None,
                "model": None, "effort": None, "started_at": None, "ended_at": None, "wall_s": 0,
                "active_s": 0, "requests": 0, "tool_calls": 0, "input": 0, "cache_write_5m": 0,
                "cache_write_1h": 0, "cache_read": 0, "output": 0, "thinking": 0, "cost": 0,
                "unpriced": 0, "fast": 0, "version": None, "last_epoch": None, "first_epoch": None}

    def apply_meta(self, a, path):
        mp = path[:-6] + ".meta.json"
        try:
            with open(mp) as f:
                m = json.load(f)
        except Exception:
            return
        a["role"] = m.get("agentType") or a["role"]
        a["parent_agent_id"] = m.get("parentAgentId")
        a["spawn_depth"] = m.get("spawnDepth", a["spawn_depth"])
        a["description"] = m.get("description") or a["description"]
        if m.get("model") and not a["model"]:
            a["model"] = m["model"]

    def file(self, path, proj, sid, aid):
        st = os.stat(path)
        row = self.conn.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()
        a = self.agent_row(sid, aid, proj)
        if aid != "main":
            self.apply_meta(a, path)
        offset = 0
        if row:
            if row["size"] == st.st_size and row["mtime"] == int(st.st_mtime):
                self.save_agent(a, partial=True)
                return
            offset = row["offset"]
            if st.st_size < offset:  # rewritten: start over for this agent
                offset = 0
                self.conn.execute("DELETE FROM requests WHERE session=? AND agent_id=?", (sid, aid))
                a.update(active_s=0, tool_calls=0, last_epoch=None, first_epoch=None, started_at=None)
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read()
        cut = data.rfind(b"\n")
        data = data[:cut + 1] if cut >= 0 else b""
        reqs = {}
        for raw in data.split(b"\n"):
            if not raw.strip():
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            self.line(d, a, sid, aid, reqs, path)
        for key, r in reqs.items():
            tok = {b: r[b] for b in BUCKETS}
            cost = cost_of(self.prices, r["model"], tok, r["fast"])
            if cost is None:
                if r["model"] not in self.unknown:
                    self.unknown.add(r["model"])
                    self.warn("unknown model %r: its cost is left empty (add it to prices.json)" % r["model"])
            elif r["fast"] and not price_for(self.prices, r["model"]).get("fast_multiplier"):
                self.warn("fast mode on %s: no fast price known, list price used" % r["model"])
            self.conn.execute("INSERT OR REPLACE INTO requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (key, sid, aid, r["ts"], r["epoch"], r["model"], r["effort"], r["input"],
                               r["cache_write_5m"], r["cache_write_1h"], r["cache_read"], r["output"],
                               r["thinking"], cost, int(r["fast"])))
        self.touched.add((sid, aid))
        self.save_agent(a)
        self.conn.execute("INSERT OR REPLACE INTO files VALUES(?,?,?,?)",
                          (path, st.st_size, int(st.st_mtime), offset + len(data)))

    def line(self, d, a, sid, aid, reqs, path):
        if aid == "main" and d.get("isSidechain"):
            return
        self.lines += 1
        ep = epoch_of(d.get("timestamp") or "") if d.get("timestamp") else None
        if ep is not None:
            if a["last_epoch"] is not None and ep > a["last_epoch"]:
                a["active_s"] += min(ep - a["last_epoch"], GAP_CAP)
            if a["last_epoch"] is None or ep > a["last_epoch"]:
                a["last_epoch"] = ep
            if a["first_epoch"] is None or ep < a["first_epoch"]:
                a["first_epoch"] = ep
        if d.get("version"):
            a["version"] = d["version"]
        if d.get("cwd") and a["project"].startswith("-"):  # still the encoded directory name
            a["project"] = d["cwd"]
        if d.get("type") != "assistant":
            return
        m = d.get("message") or {}
        if not isinstance(m, dict):
            return
        if a["role"] == "unknown" and d.get("attributionAgent"):
            a["role"] = d["attributionAgent"]
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                a["tool_calls"] += 1
        if m.get("model") == "<synthetic>":
            return
        u = m.get("usage") if isinstance(m.get("usage"), dict) else {}
        for field, get in NEEDED:
            if get(d, m, u) is None:
                self.missing.setdefault(field, d.get("version") or "unknown")
        if not u or not m.get("model"):
            return
        key = "%s|%s|%s" % (sid, aid, d.get("requestId") or m.get("id") or d.get("uuid"))
        tok = usage_tokens(u)
        r = reqs.get(key)
        if r is None:
            old = self.conn.execute("SELECT * FROM requests WHERE key=?", (key,)).fetchone()
            r = dict(old) if old else {"ts": d.get("timestamp"), "epoch": ep, "model": m["model"],
                                       "effort": d.get("effort") or d.get("perTurnEffort"), "fast": 0,
                                       **{k: 0 for k in tok}}
            reqs[key] = r
        for k, v in tok.items():
            r[k] = max(r[k], v)  # split lines of one response repeat the usage, never add it
        if u.get("speed") == "fast":
            r["fast"] = 1

    def save_agent(self, a, partial=False):
        cols = ["session", "agent_id", "project", "role", "parent_agent_id", "spawn_depth", "description",
                "model", "effort", "started_at", "ended_at", "wall_s", "active_s", "requests", "tool_calls",
                "input", "cache_write_5m", "cache_write_1h", "cache_read", "output", "thinking", "cost",
                "unpriced", "fast", "version", "last_epoch", "first_epoch"]
        if a["first_epoch"] is not None:
            a["started_at"] = iso_of(a["first_epoch"])
            a["ended_at"] = iso_of(a["last_epoch"])
            a["wall_s"] = a["last_epoch"] - a["first_epoch"]
        self.conn.execute("INSERT OR REPLACE INTO agents(%s) VALUES(%s)" % (",".join(cols), ",".join("?" * len(cols))),
                          [a[c] for c in cols])

    def finish(self):
        for sid, aid in self.touched:
            self.rollup(sid, aid)
        self.conn.commit()

    def rollup(self, sid, aid):
        q = self.conn.execute(
            "SELECT COUNT(*) n, SUM(input) i, SUM(cache_write_5m) w5, SUM(cache_write_1h) w1, "
            "SUM(cache_read) cr, SUM(output) o, SUM(thinking) t, SUM(cost) c, "
            "SUM(cost IS NULL) up, MAX(fast) f FROM requests WHERE session=? AND agent_id=?", (sid, aid)).fetchone()
        by_model = self.conn.execute(
            "SELECT model, SUM(COALESCE(cost,0)) c, COUNT(*) n FROM requests WHERE session=? AND agent_id=? "
            "GROUP BY model ORDER BY c DESC, n DESC", (sid, aid)).fetchall()
        efforts = self.conn.execute(
            "SELECT effort, COUNT(*) n FROM requests WHERE session=? AND agent_id=? AND effort IS NOT NULL "
            "GROUP BY effort ORDER BY n DESC", (sid, aid)).fetchall()
        self.conn.execute(
            "UPDATE agents SET requests=?, input=?, cache_write_5m=?, cache_write_1h=?, cache_read=?, output=?, "
            "thinking=?, cost=?, unpriced=?, fast=?, model=COALESCE(?, model), effort=? WHERE session=? AND agent_id=?",
            (q["n"], q["i"] or 0, q["w5"] or 0, q["w1"] or 0, q["cr"] or 0, q["o"] or 0, q["t"] or 0,
             q["c"] or 0, q["up"] or 0, q["f"] or 0, by_model[0]["model"] if by_model else None,
             "/".join(e["effort"] for e in efforts) or None, sid, aid))

    def reprice(self):
        for r in self.conn.execute("SELECT * FROM requests").fetchall():
            tok = {b: r[b] for b in BUCKETS}
            self.conn.execute("UPDATE requests SET cost=? WHERE key=?",
                              (cost_of(self.prices, r["model"], tok, r["fast"]), r["key"]))
        for r in self.conn.execute("SELECT session, agent_id FROM agents").fetchall():
            self.rollup(r["session"], r["agent_id"])
        self.conn.commit()


def cmd_collect(args):
    conn = connect()
    c = Collector(conn, load_prices())
    if args.reprice:
        c.reprice()
    c.scan(config_dir())
    if not args.quiet:
        n = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        r = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        print("collected %d new lines; db has %d agents, %d requests (%s)" % (c.lines, n, r, db_path()))
    return 0


# ---------------------------------------------------------------- outcome

OUTCOMES = {"pass": "pass", "review": "review", "fail": "fail"}
KINDS = ("build", "layout", "investigate", "scout", "review", "other")


def cmd_outcome(args):
    conn = connect()
    rows = conn.execute("SELECT agent_id FROM agents WHERE agent_id LIKE ? AND agent_id != 'main'",
                        (args.agent + "%",)).fetchall()
    ids = sorted({r["agent_id"] for r in rows})
    exact = [i for i in ids if i == args.agent]
    if len(exact) == 1:
        ids = exact
    if len(ids) > 1:
        print("cc-usage: %r is ambiguous: %s" % (args.agent, ", ".join(ids[:6])), file=sys.stderr)
        return 2
    if not ids:
        print("cc-usage: note: no collected agent matches %r yet; stored as given and matched at report time"
              % args.agent, file=sys.stderr)
    aid = ids[0] if ids else args.agent
    retry = args.retry_of
    conn.execute("INSERT INTO outcomes(agent_id, outcome, kind, missed, retry_of, pair, note, ts) VALUES(?,?,?,?,?,?,?,?)",
                 (aid, args.outcome, args.kind, args.missed, retry, args.pair, args.note,
                  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    conn.commit()
    print("recorded %s for %s%s" % (args.outcome, aid, " (kind %s)" % args.kind if args.kind else ""))
    return 0


# ---------------------------------------------------------------- report

def parse_since(s):
    if not s:
        return None
    m = re.fullmatch(r"(\d+)([dhw])", s)
    if m:
        n, u = int(m.group(1)), m.group(2)
        delta = timedelta(days={"d": n, "w": 7 * n, "h": 0}[u], hours=n if u == "h" else 0)
        return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%SZ")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    raise SystemExit("cc-usage: --since takes 7d, 12h, 2w or YYYY-MM-DD")


def resolve(ids, ref):
    if not ref:
        return None
    if ref in ids:
        return ref
    m = [i for i in ids if i.startswith(ref)]
    return m[0] if len(m) == 1 else None


def load(args):
    conn = connect()
    where, par = ["1=1"], []
    since = parse_since(args.since)
    if since:
        where.append("started_at >= ?")
        par.append(since)
    if args.project:
        where.append("LOWER(project) LIKE ?")
        par.append("%" + args.project.lower() + "%")
    if args.session:
        where.append("session LIKE ?")
        par.append(args.session + "%")
    agents = [dict(r) for r in conn.execute("SELECT * FROM agents WHERE " + " AND ".join(where), par)]
    for a in agents:
        a["id"] = a["agent_id"] if a["agent_id"] != "main" else "main:" + a["session"][:8]
        a["cost"] = a["cost"] or 0
        a["tokens"] = a["input"] + a["cache_write_5m"] + a["cache_write_1h"] + a["cache_read"] + a["output"]
        a["outcome"] = a["kind"] = a["missed"] = a["pair"] = a["retry_of"] = a["note"] = None
    ids = [a["agent_id"] for a in agents if a["agent_id"] != "main"]
    by_id = {a["agent_id"]: a for a in agents if a["agent_id"] != "main"}
    for o in conn.execute("SELECT * FROM outcomes ORDER BY id"):
        aid = resolve(ids, o["agent_id"])
        if aid:
            a = by_id[aid]
            a.update(outcome=o["outcome"], kind=o["kind"], missed=o["missed"], pair=o["pair"], note=o["note"],
                     retry_of=resolve(ids, o["retry_of"]) or o["retry_of"])
    keys = {(a["session"], a["agent_id"]) for a in agents}
    reqs = [dict(r) for r in conn.execute("SELECT session, agent_id, ts, cost, model, effort FROM requests")
            if (r["session"], r["agent_id"]) in keys]
    return agents, reqs, by_id


def fmt_n(n):
    n = n or 0
    for u, d in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if n >= d:
            return "%.2f%s" % (n / d, u) if n < 100 * d else "%.0f%s" % (n / d, u)
    return str(int(n))


def fmt_c(c):
    return "$%.2f" % c if c >= 0.005 or c == 0 else "$%.3f" % c


def fmt_t(s):
    s = int(s or 0)
    if s >= 3600:
        return "%dh%02dm" % (s // 3600, s % 3600 // 60)
    return "%dm%02ds" % (s // 60, s % 60) if s >= 60 else "%ds" % s


def eff(a):
    return a["effort"] or "-"


def model_s(a):
    return (a["model"] or "?").replace("claude-", "")


def build_sections(agents, reqs, by_id):
    S = []
    total = sum(a["cost"] for a in agents) or 0
    workers = [a for a in agents if a["role"] != "main"]
    # (a) totals by role
    roles = {}
    for a in agents:
        r = roles.setdefault(a["role"], dict(n=0, input=0, cw=0, cr=0, output=0, cost=0, wall=0, active=0))
        r["n"] += 1
        r["input"] += a["input"]
        r["cw"] += a["cache_write_5m"] + a["cache_write_1h"]
        r["cr"] += a["cache_read"]
        r["output"] += a["output"]
        r["cost"] += a["cost"]
        r["wall"] += a["wall_s"] or 0
        r["active"] += a["active_s"] or 0
    rows = []
    for name, r in sorted(roles.items(), key=lambda kv: -kv[1]["cost"]):
        rows.append([name, r["n"], fmt_n(r["input"]), fmt_n(r["cw"]), fmt_n(r["cr"]), fmt_n(r["output"]),
                     fmt_c(r["cost"]), fmt_t(r["wall"]), fmt_t(r["active"]),
                     "%.1f%%" % (100 * r["cost"] / total) if total else "-"])
    wc = sum(a["cost"] for a in workers)
    mc = total - wc
    rows.append(["ALL", len(agents), fmt_n(sum(a["input"] for a in agents)),
                 fmt_n(sum(a["cache_write_5m"] + a["cache_write_1h"] for a in agents)),
                 fmt_n(sum(a["cache_read"] for a in agents)), fmt_n(sum(a["output"] for a in agents)),
                 fmt_c(total), fmt_t(sum(a["wall_s"] or 0 for a in agents)),
                 fmt_t(sum(a["active_s"] or 0 for a in agents)), "100%"])
    note = "main %s (%.0f%%), workers %s (%.0f%%). Wall time overlaps for parallel agents; active time sums gaps up to %ds." % (
        fmt_c(mc), 100 * mc / total if total else 0, fmt_c(wc), 100 * wc / total if total else 0, GAP_CAP)
    S.append(dict(id="roles", title="Totals by role", headers=["role", "agents", "input", "cache write", "cache read",
                  "output", "cost", "wall", "active", "share"], rows=rows, note=note))
    # (b) role x model x effort x kind
    groups = {}
    for a in workers:
        groups.setdefault((a["role"], model_s(a), eff(a), a["kind"] or "-"), []).append(a)
    rows, rate = [], []
    for k, g in sorted(groups.items(), key=lambda kv: -sum(a["cost"] for a in kv[1])):
        c = [a["cost"] for a in g]
        cnt = {o: sum(1 for a in g if a["outcome"] == o) for o in OUTCOMES}
        rows.append(list(k) + [len(g), cnt["pass"], cnt["review"], cnt["fail"], fmt_c(statistics.median(c)),
                               fmt_c(sum(c)), fmt_t(statistics.median([a["active_s"] or 0 for a in g])),
                               fmt_n(sum(a["tokens"] for a in g))])
    S.append(dict(id="groups", title="Workers by role, model, effort and kind",
                  headers=["role", "model", "effort", "kind", "n", "pass", "review", "fail", "median cost",
                           "total cost", "median active", "tokens"], rows=rows))
    # (c) lead waves
    kids = {}
    for a in agents:
        if a["parent_agent_id"]:
            kids.setdefault(a["parent_agent_id"], []).append(a)

    def desc(a, seen):
        out = []
        for k in kids.get(a["agent_id"], []):
            if k["agent_id"] not in seen:
                seen.add(k["agent_id"])
                out.append(k)
                out += desc(k, seen)
        return out
    rows = []
    for l in [a for a in workers if a["role"] == "lead"]:
        d = desc(l, {l["agent_id"]})
        cost = l["cost"] + sum(x["cost"] for x in d)
        roles_s = ", ".join("%s %d" % (r, n) for r, n in sorted(
            {r: sum(1 for x in d if x["role"] == r) for r in {x["role"] for x in d}}.items()))
        res = [x["outcome"] for x in d if x["outcome"]]
        rows.append([l["id"], (l["description"] or "")[:40], len(d), roles_s or "-", fmt_c(l["cost"]),
                     fmt_c(cost), fmt_t(l["active_s"] + sum(x["active_s"] or 0 for x in d)),
                     "%d/%d/%d" % (res.count("pass"), res.count("review"), res.count("fail")), l["outcome"] or "-"])
    S.append(dict(id="waves", title="Lead waves (the lead plus every descendant)",
                  headers=["lead", "task", "workers", "by role", "lead cost", "wave cost", "active",
                           "pass/review/fail", "lead outcome"], rows=rows))
    # (d) cost per accepted outcome, with rework
    def root(a):
        seen = set()
        while a["retry_of"] in by_id and a["agent_id"] not in seen:
            seen.add(a["agent_id"])
            a = by_id[a["retry_of"]]
        return a
    chains = {}
    for a in workers:
        chains.setdefault(root(a)["agent_id"], []).append(a)
    per = {}
    for rid, ch in chains.items():
        r = by_id[rid]
        k = (r["role"], r["kind"] or "-")
        p = per.setdefault(k, dict(chains=0, agents=0, cost=0, acc=0))
        p["chains"] += 1
        p["agents"] += len(ch)
        p["cost"] += sum(a["cost"] for a in ch)
        p["acc"] += sum(1 for a in ch if a["outcome"] in ("pass", "review"))
    rows = [[k[0], k[1], p["chains"], p["agents"], p["acc"], fmt_c(p["cost"]),
             fmt_c(p["cost"] / p["acc"]) if p["acc"] else "n/a"] for k, p in sorted(per.items(), key=lambda kv: -kv[1]["cost"])]
    S.append(dict(id="accepted", title="Cost per accepted outcome, rework included (retry chains)",
                  headers=["first role", "kind", "chains", "agents", "accepted", "chain cost", "cost / accepted"],
                  rows=rows, note="A chain is a task and every --retry-of re-attempt of it; accepted = pass or review."))
    # (e) retries that changed model or effort
    rows = []
    for a in workers:
        p = by_id.get(a["retry_of"])
        if p and (p["model"] != a["model"] or p["effort"] != a["effort"]):
            rows.append([p["id"], "%s %s" % (p["role"], model_s(p)), eff(p), p["outcome"] or "-", fmt_c(p["cost"]),
                         a["id"], "%s %s" % (a["role"], model_s(a)), eff(a), a["outcome"] or "-", fmt_c(a["cost"]),
                         (p["missed"] or "")[:40]])
    S.append(dict(id="retries", title="Retries that changed model or effort",
                  headers=["first", "agent", "effort", "outcome", "cost", "retry", "agent", "effort", "outcome", "cost",
                           "first missed"], rows=rows))
    # (f) pair groups
    pairs = {}
    for a in workers:
        if a["pair"]:
            pairs.setdefault(a["pair"], []).append(a)
    rows = []
    for k, g in sorted(pairs.items()):
        for a in sorted(g, key=lambda x: x["started_at"] or ""):
            rows.append([k, a["id"], a["role"], model_s(a), eff(a), a["kind"] or "-", a["outcome"] or "-",
                         fmt_c(a["cost"]), fmt_t(a["active_s"]), fmt_n(a["tokens"])])
    S.append(dict(id="pairs", title="Pair groups side by side",
                  headers=["pair", "agent", "role", "model", "effort", "kind", "outcome", "cost", "active", "tokens"],
                  rows=rows))
    # (g) top 10
    rows = [[a["id"], a["role"], model_s(a), eff(a), (a["description"] or "")[:40], fmt_c(a["cost"]),
             fmt_t(a["active_s"]), fmt_n(a["tokens"]), a["outcome"] or "-"]
            for a in sorted(agents, key=lambda x: -x["cost"])[:10]]
    S.append(dict(id="top", title="Ten costliest agents",
                  headers=["agent", "role", "model", "effort", "task", "cost", "active", "tokens", "outcome"], rows=rows))
    # (h) no outcome
    none = sorted([a for a in workers if not a["outcome"]], key=lambda x: x["started_at"] or "")
    rows = [[a["id"], a["role"], model_s(a), (a["description"] or "")[:44], (a["started_at"] or "")[:16],
             fmt_c(a["cost"])] for a in none[-40:]]
    S.append(dict(id="norecord", title="Workers with no recorded outcome (%d)" % len(none),
                  headers=["agent", "role", "model", "task", "started", "cost"], rows=rows,
                  note="Record with: cc-usage outcome <id> pass|review|fail" + (
                      "; the latest 40 are shown" if len(none) > 40 else "")))
    return S


def render_text(S, header):
    out = [header, ""]
    for s in S:
        out.append("== %s ==" % s["title"])
        if not s["rows"]:
            out.append("(none)\n")
            continue
        cols = list(zip(s["headers"], *[[str(c) for c in r] for r in s["rows"]]))
        w = [max(len(str(x)) for x in col) for col in cols]
        out.append("  ".join(str(h).ljust(w[i]) for i, h in enumerate(s["headers"])))
        for r in s["rows"]:
            out.append("  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))
        if s.get("note"):
            out.append(s["note"])
        out.append("")
    return "\n".join(out)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PALETTE = 8


def svg_stack(days, roles):
    """days: [(day, {role: cost})]; stacked bars, inline SVG."""
    if not days:
        return "<p>no data</p>"
    W, H, L, B = 760, 220, 46, 24
    mx = max(sum(d[1].values()) for d in days) or 1
    bw = (W - L) / len(days)
    parts = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Spend by role per day">' % (W, H)]
    for t in range(0, 5):
        y = H - B - (H - B - 8) * t / 4
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid"/><text x="%d" y="%.1f" class="ax" text-anchor="end">%s</text>'
                     % (L, W, y, y, L - 4, y + 3, fmt_c(mx * t / 4)))
    for i, (day, v) in enumerate(days):
        y = H - B
        for j, r in enumerate(roles):
            h = (H - B - 8) * v.get(r, 0) / mx
            y -= h
            if h > 0:
                parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" class="c%d"><title>%s %s %s</title></rect>'
                             % (L + i * bw + 2, y, max(bw - 4, 1), h, j % PALETTE, esc(day), esc(r), fmt_c(v[r])))
        if len(days) <= 16 or i % max(1, len(days) // 12) == 0:
            parts.append('<text x="%.1f" y="%d" class="ax" text-anchor="middle">%s</text>' % (L + i * bw + bw / 2, H - 8, esc(day[5:])))
    parts.append("</svg>")
    leg = "".join('<span class="lg"><i class="c%d"></i>%s</span>' % (j % PALETTE, esc(r)) for j, r in enumerate(roles))
    return "".join(parts) + '<div class="legend">%s</div>' % leg


def svg_hbars(items, fmt, cls="c0"):
    if not items:
        return "<p>no data</p>"
    W, row, L = 760, 22, 230
    mx = max(v for _, v in items) or 1
    p = ['<svg viewBox="0 0 %d %d">' % (W, row * len(items) + 4)]
    for i, (lab, v) in enumerate(items):
        w = (W - L - 80) * v / mx
        p.append('<text x="%d" y="%d" class="ax" text-anchor="end">%s</text><rect x="%d" y="%d" width="%.1f" height="14" class="%s"/>'
                 '<text x="%.1f" y="%d" class="ax">%s</text>' % (L - 6, i * row + 14, esc(lab), L, i * row + 4, w, cls, L + w + 4, i * row + 15, fmt(v)))
    p.append("</svg>")
    return "".join(p)


def svg_rates(items):
    """items: [(label, pass, review, fail)] as normalised stacked bars."""
    items = [i for i in items if i[1] + i[2] + i[3]]
    if not items:
        return "<p>no outcomes recorded yet</p>"
    W, row, L = 760, 22, 230
    p = ['<svg viewBox="0 0 %d %d">' % (W, row * len(items) + 4)]
    for i, (lab, a, b, c) in enumerate(items):
        n = a + b + c
        x = L
        p.append('<text x="%d" y="%d" class="ax" text-anchor="end">%s</text>' % (L - 6, i * row + 14, esc(lab)))
        for v, cls in ((a, "ok"), (b, "rv"), (c, "bad")):
            w = (W - L - 80) * v / n
            if w:
                p.append('<rect x="%.1f" y="%d" width="%.1f" height="14" class="%s"><title>%d</title></rect>' % (x, i * row + 4, w, cls, v))
            x += w
        p.append('<text x="%.1f" y="%d" class="ax">%d%% of %d</text>' % (x + 4, i * row + 15, round(100 * (a + b) / n), n))
    p.append("</svg>")
    return "".join(p) + '<div class="legend"><span class="lg"><i class="ok"></i>pass</span><span class="lg"><i class="rv"></i>review</span><span class="lg"><i class="bad"></i>fail</span></div>'


CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1b;--mut:#6b6b66;--line:#dcdcd4;--card:#fff;--ok:#2f8f5b;--rv:#d4a017;--bad:#c0392b;
--c0:#3b6ea5;--c1:#c77d2e;--c2:#4f9a7a;--c3:#8a5aa8;--c4:#b5495b;--c5:#6f8f2f;--c6:#2f8f9a;--c7:#8a8a80}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17171a;--fg:#e8e8e3;--mut:#9a9a93;--line:#34343a;--card:#202025;--ok:#4cc38a;--rv:#e6b84a;--bad:#e5695a;
--c0:#6ea2dc;--c1:#e0a05a;--c2:#6fc3a0;--c3:#b88ad6;--c4:#e07a8c;--c5:#9bbd5a;--c6:#5fc0cc;--c7:#a8a8a0}}
:root[data-theme=dark]{--bg:#17171a;--fg:#e8e8e3;--mut:#9a9a93;--line:#34343a;--card:#202025;--ok:#4cc38a;--rv:#e6b84a;--bad:#e5695a;
--c0:#6ea2dc;--c1:#e0a05a;--c2:#6fc3a0;--c3:#b88ad6;--c4:#e07a8c;--c5:#9bbd5a;--c6:#5fc0cc;--c7:#a8a8a0}
body{background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;margin:0;padding:16px max(16px,env(safe-area-inset-left,0px));max-width:1000px;margin-inline:auto}
h1{font-size:20px}h2{font-size:16px;margin:28px 0 8px}.note,.hdr{color:var(--mut);font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:8px 0}
.scroll{overflow-x:auto}table{border-collapse:collapse;font-size:12px;width:100%}
th,td{text-align:left;padding:3px 8px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--mut)}
svg{width:100%;height:auto}.grid{stroke:var(--line)}.ax{fill:var(--mut);font-size:10px}
.c0{fill:var(--c0);background:var(--c0)}.c1{fill:var(--c1);background:var(--c1)}.c2{fill:var(--c2);background:var(--c2)}.c3{fill:var(--c3);background:var(--c3)}
.c4{fill:var(--c4);background:var(--c4)}.c5{fill:var(--c5);background:var(--c5)}.c6{fill:var(--c6);background:var(--c6)}.c7{fill:var(--c7);background:var(--c7)}
rect.ok,i.ok{fill:var(--ok);background:var(--ok)}rect.rv,i.rv{fill:var(--rv);background:var(--rv)}rect.bad,i.bad{fill:var(--bad);background:var(--bad)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;margin-top:6px}.lg i{display:inline-block;width:10px;height:10px;margin-right:4px;border-radius:2px}
"""


def render_html(S, header, agents, reqs):
    roles = [r for r, _ in sorted({(a["role"], 0) for a in agents}, key=lambda x: x[0])]
    cost_by_role = {}
    for a in agents:
        cost_by_role[a["role"]] = cost_by_role.get(a["role"], 0) + a["cost"]
    roles.sort(key=lambda r: -cost_by_role[r])
    role_of = {(a["session"], a["agent_id"]): a["role"] for a in agents}
    days = {}
    for r in reqs:
        if r["cost"] is None or not r["ts"]:
            continue
        d = days.setdefault(r["ts"][:10], {})
        role = role_of.get((r["session"], r["agent_id"]), "?")
        d[role] = d.get(role, 0) + r["cost"]
    daily = sorted(days.items())
    me = {}
    for a in agents:
        k = "%s %s" % (model_s(a), eff(a))
        me[k] = me.get(k, 0) + a["cost"]
    rate = {}
    for dim, f in (("model", model_s), ("effort", eff), ("kind", lambda a: a["kind"] or "-")):
        for a in agents:
            if a["outcome"] and a["role"] != "main":
                x = rate.setdefault("%s: %s" % (dim, f(a)), [0, 0, 0])
                x[{"pass": 0, "review": 1, "fail": 2}[a["outcome"]]] += 1
    out = ["<title>cc-usage report</title><style>%s</style>" % CSS, "<h1>cc-usage report</h1>",
           '<p class="hdr">%s</p>' % esc(header),
           '<h2>Spend by role per day</h2><div class="card">%s</div>' % svg_stack(daily, roles),
           '<h2>Cost by model and effort</h2><div class="card">%s</div>' % svg_hbars(
               sorted(me.items(), key=lambda kv: -kv[1]), fmt_c),
           '<h2>Success rate by model, effort and kind</h2><div class="card">%s</div>' % svg_rates(
               [(k, *v) for k, v in sorted(rate.items())])]
    for s in S:
        out.append("<h2>%s</h2><div class='card scroll'>" % esc(s["title"]))
        if s["rows"]:
            out.append("<table><tr>%s</tr>%s</table>" % ("".join("<th>%s</th>" % esc(h) for h in s["headers"]),
                       "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % esc(c) for c in r) for r in s["rows"])))
        else:
            out.append("<p>none</p>")
        if s.get("note"):
            out.append('<p class="note">%s</p>' % esc(s["note"]))
        out.append("</div>")
    return "\n".join(out)


def cmd_report(args):
    agents, reqs, by_id = load(args)
    if not agents:
        print("cc-usage: nothing to report (run `cc-usage collect`, or loosen the filters)")
        return 0
    unpriced = sum(a["unpriced"] or 0 for a in agents)
    header = ("cc-usage report. Cost is the API list-price equivalent (prices.json as of %s), not a bill; "
              "on a subscription it is a comparison figure.%s" % (
                  load_prices().get("as_of"),
                  " %d requests have an unknown model and no cost." % unpriced if unpriced else ""))
    S = build_sections(agents, reqs, by_id)
    print(render_text(S, header))
    if args.html:
        with open(args.html, "w") as f:
            f.write(render_html(S, header, agents, reqs))
        print("wrote " + args.html)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cc-usage", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="scan transcripts into the database")
    c.add_argument("--quiet", action="store_true")
    c.add_argument("--reprice", action="store_true", help="recompute every cost from the current prices")
    c.set_defaults(fn=cmd_collect)
    o = sub.add_parser("outcome", help="record whether a worker's task succeeded")
    o.add_argument("agent")
    o.add_argument("outcome", choices=sorted(OUTCOMES))
    o.add_argument("--kind", choices=KINDS)
    o.add_argument("--missed")
    o.add_argument("--retry-of", dest="retry_of")
    o.add_argument("--pair")
    o.add_argument("--note")
    o.set_defaults(fn=cmd_outcome)
    r = sub.add_parser("report", help="tables, optionally one HTML file")
    r.add_argument("--since")
    r.add_argument("--project")
    r.add_argument("--session")
    r.add_argument("--html")
    r.set_defaults(fn=cmd_report)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    finally:
        while _OPEN:
            _OPEN.pop().close()


if __name__ == "__main__":
    sys.exit(main())
