#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thesis Registry v2 —— 技术命题的证据库。设计见 references/registry-v2-design.md。

  - 事件（证据，不可变）与命题（定义）分开存，用 link 连接，一个事件一条 link；
  - 只持久化"决策"：命题定义、事件、link、显式决策（merge / retire / revise / supersede）。
    state / confidence / thesis_type / entities 全部由 link 派生，读取时计算 —— 所以重跑、
    改裁决、撤销都只是替换决策，派生值自动正确；
  - 入库以 run（= WINDOW_START_DATE）为单位的事务：同一 run 重跑整批替换，事件按 event_key 去重；
  - 状态放在工作目录（默认 ./state，或 --state / $TECH_BRIEFING_STATE），与 skill 代码分离。

CLI（全局参数 --state DIR）：
  candidates --events-dir D [--run-date R]       为每个事件写入 thesis_candidates
  ingest     --events-dir D --run-date R [--report collect_report.json] [--backfill]
  gaps       --until R                           列出漏跑的窗口日期（需补跑）
  report     --run-date R [--out FILE]           第 7 章输入：本轮命题的前后对比
  show TH-0001 | search 关键词 | stats
  merge --source A --target B --reason ... | retire --id X --reason ...
  revise --id X --statement ... --reason ...  | supersede --old A --new B --reason ...
"""
import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import TAXONOMY, TaxonomyError  # noqa: E402
from events import event_key as compute_event_key  # noqa: E402

SCHEMA_VERSION = 2
ONTOLOGY = json.loads((Path(__file__).parent / "thesis_ontology.json").read_text(encoding="utf-8"))
CM = ONTOLOGY["confidence_model"]
LC = ONTOLOGY["thesis_lifecycle"]
RULES = ONTOLOGY["thesis_rules"]
CHANGE_TYPES = {ct["id"] for ct in ONTOLOGY["change_types"]}
SH_TZ = timezone(timedelta(hours=8))

SUPPORT = ("supports", "refines")
RELATIONS = ("supports", "contradicts", "refines")
ACTIONS = ("attach", "new", "none")
STRONG = ("A+", "A")
NEW_REF = "NEW:"


class RegistryError(Exception):
    pass


class ValidationError(RegistryError):
    def __init__(self, errors: list[str]):
        super().__init__(f"{len(errors)} 个校验错误")
        self.errors = errors


class LockTimeout(RegistryError):
    pass


def default_state_dir() -> Path:
    return Path(os.environ.get("TECH_BRIEFING_STATE") or (Path.cwd() / "state"))


def _today() -> str:
    return datetime.now(SH_TZ).strftime("%Y-%m-%d")


def _to_date(s) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)).date()
    except ValueError:
        try:
            return date.fromisoformat(str(s)[:10])
        except ValueError:
            return None


def _bonus(value: int, table) -> int:
    """table = [[阈值, 分], ...]，取满足的最高档。"""
    got = 0
    for threshold, pts in table:
        if value >= threshold:
            got = pts
    return got


def _level2(path: str) -> str:
    """叶子 → 二级域；本身就是二级域（如 B2）时原样返回。"""
    try:
        return TAXONOMY.leaf(path)["level2"]
    except (TaxonomyError, KeyError):
        return path.split(".")[0]


def _is_leaf(path: str) -> bool:
    return path in set(TAXONOMY.leaf_ids())


# ====================================================================
class Registry:
    def __init__(self, state_dir: Path | None = None):
        self.state_dir = Path(state_dir) if state_dir else default_state_dir()
        self.path = self.state_dir / "thesis_registry.json"
        self.log_path = self.state_dir / "registry_log.jsonl"
        self.lock_path = self.state_dir / ".registry.lock"
        self._locked = False
        self._cache: dict = {}
        self._rollback_notes: list[str] = []
        self.data = self._load()

    # ---------- 存储 ----------
    def _load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": SCHEMA_VERSION, "runs": [], "events": {},
                    "theses": {}, "links": [], "decisions": []}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise RegistryError(f"{self.path} 不是 v2 registry（schema_version="
                                f"{data.get('schema_version')}）；v1 数据不迁移，请换一个 state 目录")
        return data

    def lock(self, timeout: float = 10.0):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self._locked = True
                self.data = self._load()        # 拿到锁后重读，避免覆盖别人刚写的内容
                self._cache = {}
                return self
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise LockTimeout(f"registry 被占用：{self.lock_path}。确认没有其他进程在写后可手动删除")
                time.sleep(0.2)

    def unlock(self):
        if self._locked:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass
            self._locked = False

    def __enter__(self):
        return self.lock()

    def __exit__(self, *exc):
        self.unlock()

    def save(self):
        if not self._locked:
            raise RegistryError("写入前必须持锁（with Registry(...) as reg）")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def _log(self, op: str, **payload):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        rec = {"at": datetime.now(SH_TZ).isoformat(timespec="seconds"), "op": op, **payload}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------- 基础查询 ----------
    @property
    def runs(self) -> list[dict]:
        return sorted(self.data["runs"], key=lambda r: r["run_date"])

    def run_dates(self, as_of: str | None = None) -> list[str]:
        return [r["run_date"] for r in self.runs if as_of is None or r["run_date"] <= as_of]

    def latest_run(self) -> str | None:
        ds = self.run_dates()
        return ds[-1] if ds else None

    def previous_run(self, run_date: str) -> str | None:
        prev = [d for d in self.run_dates() if d < run_date]
        return prev[-1] if prev else None

    def _decisions(self, as_of: str | None) -> list[dict]:
        return [d for d in self.data["decisions"] if as_of is None or d["date"] <= as_of]

    def _index(self, as_of: str) -> tuple[dict, dict]:
        """按 as_of 缓存：命题 → 合并链终点；终点 → 归属它的 links。数据变动时清空。"""
        key = ("idx", as_of)
        if key not in self._cache:
            merges = {d["source"]: d["target"] for d in self._decisions(as_of) if d["type"] == "merge"}

            def final(t):
                seen = set()
                while t in merges and t not in seen:
                    seen.add(t)
                    t = merges[t]
                return t

            target = {t: final(t) for t in self.data["theses"]}
            owned: dict[str, list] = {}
            for l in self.data["links"]:
                if l["decided_in"] <= as_of:
                    owned.setdefault(target.get(l["thesis_id"], l["thesis_id"]), []).append(l)
            self._cache[key] = (target, owned)
        return self._cache[key]

    def _merge_target(self, tid: str, as_of: str) -> str:
        return self._index(as_of)[0].get(tid, tid)

    def theses_as_of(self, as_of: str | None) -> list[str]:
        return sorted(t for t, th in self.data["theses"].items()
                      if as_of is None or th["created_in"] <= as_of)

    # ---------- 派生视图 ----------
    def view(self, tid: str, as_of: str | None = None) -> dict:
        """命题在 as_of（含）时刻的派生状态。as_of=None 表示最新。"""
        if tid not in self.data["theses"]:
            raise RegistryError(f"不存在的命题 {tid}")
        th = self.data["theses"][tid]
        as_of = as_of or self.latest_run() or th["created_in"]
        ck = ("view", tid, as_of)
        if ck in self._cache:
            return self._cache[ck]
        self._cache[ck] = v = self._view(tid, th, as_of)
        return v

    def _view(self, tid: str, th: dict, as_of: str) -> dict:
        decisions = self._decisions(as_of)
        statement = th["statement"]
        for d in decisions:
            if d["type"] == "revise" and d["thesis_id"] == tid:
                statement = d["new_statement"]

        base = {"id": tid, "name": th["name"], "statement": statement,
                "scope_leaves": th["scope_leaves"], "change_types": th["change_types"],
                "created_in": th["created_in"], "as_of": as_of}

        merged_into = self._merge_target(tid, as_of)
        if merged_into != tid:
            return {**base, "state": "merged", "merged_into": merged_into, "confidence": "Low",
                    "score": 0, "breakdown": {}, "type": None, "entities": [],
                    "support": [], "contradicts": []}

        links = self._index(as_of)[1].get(tid, [])
        events = self.data["events"]
        sup = [(l, events[l["event_key"]]) for l in links if l["relation"] in SUPPORT]
        con = [(l, events[l["event_key"]]) for l in links if l["relation"] == "contradicts"]

        ref = _to_date(as_of)
        entities = sorted({e["entity"] for _, e in sup if e.get("entity")})
        forms = {e.get("evidence_form") for _, e in sup if e.get("evidence_form")}
        weeks = {_to_date(e["first_publish"]).isocalendar()[:2] for _, e in sup
                 if _to_date(e["first_publish"])}

        bd = {"strength": max((CM["strength"].get(e["rating"], 0) for _, e in sup), default=0),
              "entities": _bonus(len(entities), CM["entities_bonus"]),
              "forms": _bonus(len(forms), CM["forms_bonus"]),
              "persistence": _bonus(len(weeks), CM["weeks_bonus"]),
              "adoption": CM["adoption_bonus"] if CM["adoption_form"] in forms else 0,
              "counter": 0, "stale": 0}
        recent_con = [e for _, e in con
                      if _to_date(e["first_publish"]) and
                      (ref - _to_date(e["first_publish"])).days <= CM["counter_window_days"]]
        bd["counter"] = -sum(CM["counter_penalty"].get(e["rating"], 1) for e in recent_con)
        if sup and not any(_to_date(e["first_publish"]) and
                           (ref - _to_date(e["first_publish"])).days <= CM["stale_days"]
                           for _, e in sup):
            bd["stale"] = -CM["stale_penalty"]
        score = sum(bd.values()) if sup else 0
        confidence = next(name for name, th_ in CM["levels"] if score >= th_)
        if not sup:
            confidence = "Low"

        # ---- 生命周期（按实际 run 计数）----
        dates = self.run_dates(as_of)
        idx = {d: i for i, d in enumerate(dates)}
        now_i = len(dates) - 1
        created_i = idx.get(th["created_in"], 0)
        sup_runs = [idx[l["decided_in"]] for l, _ in sup if l["decided_in"] in idx]
        since_support = now_i - max(sup_runs) if sup_runs else now_i - created_i
        distinct_sup = len({l["event_key"] for l, _ in sup})
        is_established = any(e["rating"] in STRONG for _, e in sup) or distinct_sup >= 2
        contested = any(e["rating"] in STRONG and
                        (ref - _to_date(e["first_publish"])).days <= LC["contested_window_days"]
                        for _, e in con if _to_date(e["first_publish"]))
        retire = next((d for d in decisions if d["type"] in ("retire", "supersede")
                       and d.get("thesis_id", d.get("old")) == tid), None)

        reason = ""
        if retire:
            state, reason = "retired", retire.get("reason", retire["type"])
        elif not is_established and now_i - created_i >= LC["proposed_ttl_runs"]:
            state, reason = "retired", "未获二次证据"
        elif since_support >= LC["dormant_after_runs"] + LC["retire_after_dormant_runs"]:
            state, reason = "retired", "长期沉寂"
        elif contested:
            state = "contested"
        elif since_support >= LC["dormant_after_runs"]:
            state = "dormant"
        elif is_established:
            state = "active"
        else:
            state = "proposed"

        def brief(pairs):
            return [{"event_key": l["event_key"], "title": e["title"], "entity": e.get("entity", ""),
                     "rating": e["rating"], "first_publish": e["first_publish"],
                     "decided_in": l["decided_in"], "relation": l["relation"]} for l, e in pairs]

        return {**base, "state": state, "state_reason": reason, "confidence": confidence,
                "score": score, "breakdown": bd,
                "type": "Convergence Thesis" if len(entities) >= 2 else "Frontier Thesis",
                "entities": entities, "runs_since_support": since_support,
                "support": brief(sup), "contradicts": brief(con)}

    # ---------- 召回 ----------
    def candidates(self, ev: dict, run_date: str | None = None) -> list[dict]:
        """结构化召回。run_date 给定时只看该 run 之前已存在的命题（重跑同一 run 时
        排除它上一次尝试新建的命题），状态按上一个 run 计算。"""
        if run_date:
            as_of = self.previous_run(run_date)
            pool = [t for t in self.theses_as_of(as_of)] if as_of else []
        else:
            as_of = self.latest_run()
            pool = self.theses_as_of(as_of)
        w = RULES["recall_weights"]
        path = ev.get("primary_path") or ""
        lvl2 = _level2(path) if path else ""
        rel = ev.get("related_domains") or []
        cts = set(ev.get("change_types") or [])
        out = []
        for tid in pool:
            v = self.view(tid, as_of)
            if v["state"] not in RULES["recall_states"]:
                continue
            leaves = set(v["scope_leaves"])
            lv2s = {_level2(x) for x in leaves}
            score, reasons = 0, []
            if path in leaves:
                score += w["same_leaf"]
                reasons.append(f"同叶子 {path}")
            elif lvl2 and lvl2 in lv2s:
                score += w["same_level2"]
                reasons.append(f"同二级域 {lvl2}")
            hit_rel = [r for r in rel if r in leaves or _level2(r) in lv2s]
            if hit_rel:
                score += w["related_domain"]
                reasons.append(f"关联域 {hit_rel[0]}")
            ct_hit = sorted(cts & set(v["change_types"]))
            if ct_hit:
                score += min(len(ct_hit) * w["change_type_each"], w["change_type_max"])
                reasons.append("变化类型 " + "/".join(ct_hit))
            if ev.get("entity") and ev["entity"] in v["entities"]:
                score += w["same_entity"]
                reasons.append(f"同实体 {ev['entity']}")
            if score >= RULES["candidate_min_score"]:
                out.append({"id": tid, "score": score, "state": v["state"],
                            "confidence": v["confidence"], "statement": v["statement"],
                            "reasons": reasons})
        out.sort(key=lambda x: (-x["score"], x["id"]))
        return out[:RULES["candidate_limit"]]

    def search(self, keyword: str) -> list[dict]:
        kw = keyword.lower()
        hits = []
        for tid, th in sorted(self.data["theses"].items()):
            blob = " ".join([th["name"], th["statement"], th.get("object", ""),
                             th.get("consequence", "")]).lower()
            if kw in blob:
                v = self.view(tid)
                hits.append({"id": tid, "name": th["name"], "state": v["state"],
                             "confidence": v["confidence"], "statement": v["statement"]})
        return hits

    # ---------- 入库（事务） ----------
    def _rollback_run(self, run_date: str):
        d = self.data
        self._cache = {}
        d["links"] = [l for l in d["links"] if l["decided_in"] != run_date]
        removed = {k for k, v in d["theses"].items() if v["created_in"] == run_date}
        d["theses"] = {k: v for k, v in d["theses"].items() if v["created_in"] != run_date}
        refs = ("source", "target", "thesis_id", "old", "new")
        dropped = [x for x in d["decisions"] if any(x.get(r) in removed for r in refs)]
        d["decisions"] = [x for x in d["decisions"] if x not in dropped]
        self._rollback_notes = [f"重跑 {run_date}：撤销了引用本轮旧命题的 {x['type']} 决策 "
                                f"{ {r: x[r] for r in refs if r in x} }" for x in dropped]
        for k in list(d["events"]):
            ev = d["events"][k]
            ev["seen_in_runs"] = [r for r in ev["seen_in_runs"] if r != run_date]
            ev.get("labels", {}).pop(run_date, None)
            if not ev["seen_in_runs"]:
                del d["events"][k]
        d["runs"] = [r for r in d["runs"] if r["run_date"] != run_date]

    def _next_id(self) -> str:
        n = max((int(t.split("-")[1]) for t in self.data["theses"]), default=0)
        return RULES["id_format"] % (n + 1)

    def validate_batch(self, run_date: str, events: list[dict]) -> tuple[list[str], list[str]]:
        """返回 (errors, warnings)。只读，不改 registry。"""
        errors, warnings = [], []
        valid_leaves = set(TAXONOMY.leaf_ids())
        aliases = {}
        for ev in events:
            nt = (ev.get("thesis_decision") or {}).get("new_thesis") or {}
            if nt.get("alias"):
                if nt["alias"] in aliases:
                    errors.append(f"{ev['event_id']}: alias {nt['alias']} 与 {aliases[nt['alias']]} 重复")
                aliases[nt["alias"]] = ev["event_id"]

        seen_keys = {}
        for ev in events:
            eid = ev.get("event_id", "?")
            if not ev.get("event_key"):
                errors.append(f"{eid}: 缺 event_key（先跑 events.py normalize）")
                continue
            if ev["event_key"] != compute_event_key(ev):
                errors.append(f"{eid}: event_key 与来源不符（来源改过？重跑 events.py normalize）")
            if ev["event_key"] in seen_keys:
                errors.append(f"{eid}: 与 {seen_keys[ev['event_key']]} 是同一事件")
            seen_keys[ev["event_key"]] = eid

            dec = ev.get("thesis_decision")
            rating = ev.get("rating")
            if dec is None:
                if rating in STRONG:
                    errors.append(f"{eid}: A/A+ 事件缺 thesis_decision")
                continue
            action = dec.get("action")
            if action not in ACTIONS:
                errors.append(f"{eid}: action={action} 不在 {ACTIONS}")
                continue
            if action == "none":
                if rating in STRONG:
                    errors.append(f"{eid}: A/A+ 事件不能是 none，必须 attach 或 new")
                continue
            relation = dec.get("relation", "supports")
            if relation not in RELATIONS:
                errors.append(f"{eid}: relation={relation} 不在 {RELATIONS}")
            if not (dec.get("rationale") or "").strip():
                errors.append(f"{eid}: 缺 rationale")

            cands = {c["id"] for c in self.candidates(ev, run_date)}
            if action == "attach":
                tid = dec.get("thesis_id") or ""
                if tid.startswith(NEW_REF):
                    if tid[len(NEW_REF):] not in aliases:
                        errors.append(f"{eid}: 引用了本批次不存在的新命题 {tid}")
                    continue
                if tid not in self.data["theses"] or self.data["theses"][tid]["created_in"] >= run_date:
                    errors.append(f"{eid}: attach 目标 {tid} 不存在")
                    continue
                st = self.view(tid, self.previous_run(run_date))["state"]
                if st in ("retired", "merged"):
                    errors.append(f"{eid}: attach 目标 {tid} 已 {st}")
                if tid not in cands and not (dec.get("override_reason") or "").strip():
                    errors.append(f"{eid}: {tid} 不在召回候选中，需写 override_reason")
            else:  # new
                if relation == "contradicts":
                    errors.append(f"{eid}: 新建命题不能是 contradicts")
                nt = dec.get("new_thesis") or {}
                for f in ("name", "statement", "object", "consequence"):
                    if not (nt.get(f) or "").strip():
                        errors.append(f"{eid}: new_thesis 缺 {f}")
                leaves = nt.get("scope_leaves") or []
                if not 1 <= len(leaves) <= RULES["max_scope_leaves"]:
                    errors.append(f"{eid}: scope_leaves 需 1–{RULES['max_scope_leaves']} 个，实际 {len(leaves)}")
                bad = [x for x in leaves if x not in valid_leaves]
                if bad:
                    errors.append(f"{eid}: scope_leaves 不是叶子 {bad}（命题不能停在二级域）")
                cts = nt.get("change_types") or []
                if not cts or set(cts) - CHANGE_TYPES:
                    errors.append(f"{eid}: new_thesis.change_types 为空或含未知类型 {cts}")
                rejected = {r.get("id") for r in dec.get("rejected") or [] if (r.get("reason") or "").strip()}
                missing = sorted(cands - rejected)
                if missing:
                    errors.append(f"{eid}: 新建命题须逐个说明为何不归入候选，缺 {missing}")
                for tid, th in self.data["theses"].items():
                    if th["created_in"] < run_date and set(th["scope_leaves"]) == set(leaves) \
                            and th.get("object") == nt.get("object"):
                        warnings.append(f"{eid}: 新命题与 {tid} 的范围和 object 相同，疑似重复命题")

        # 疑似重复事件：同实体、同 primary_path、首发相差 < 24h、event_key 不同
        pool = [(e["event_id"], e) for e in events if e.get("event_key")] + \
               [(f"registry:{k}", {**v, "event_key": k}) for k, v in self.data["events"].items()]
        for i, (a, ea) in enumerate(pool):
            for b, eb in pool[i + 1:]:
                if ea["event_key"] == eb["event_key"] or a.startswith("registry:"):
                    continue
                if ea.get("entity") and ea.get("entity") == eb.get("entity") \
                        and ea.get("primary_path") == eb.get("primary_path"):
                    ta = ea.get("first_publish_shanghai") or ea.get("first_publish")
                    tb = eb.get("first_publish_shanghai") or eb.get("first_publish")
                    try:
                        gap = abs((datetime.fromisoformat(str(ta)) -
                                   datetime.fromisoformat(str(tb))).total_seconds())
                    except (TypeError, ValueError):
                        continue
                    if gap < 86400:
                        warnings.append(f"{a} 与 {b}: 同实体、同叶子、首发相差 < 24h，疑似同一事件")
        return errors, warnings

    def ingest_run(self, run_date: str, events: list[dict], window: list[str] | None = None,
                   backfill: bool = False) -> dict:
        """事务入库：先校验全部，任何错误整批不写；同一 run 重跑整批替换。

        backfill=True 用于补跑漏掉的窗口：run_date 必须早于最近一次 run 且 registry 中尚无此 run。
        补跑只能挂到当时已存在的命题；与后续 run 重叠的事件保留后续裁决，不改写历史。
        """
        if not self._locked:
            raise RegistryError("ingest 必须持锁")
        latest = self.latest_run()
        self._rollback_notes = []
        if backfill:
            if not latest or run_date >= latest:
                raise RegistryError("补跑只用于早于最近一次 run 的缺失日期；最新日期直接 ingest")
            if run_date in self.run_dates():
                raise RegistryError(f"{run_date} 已入库；补跑不能覆盖已有 run")
        elif latest and run_date < latest:
            raise RegistryError(f"只能入库最新 run 或重跑最近一次 run（最近一次是 {latest}）；"
                                f"补跑漏掉的日期用 --backfill")

        snapshot = json.loads(json.dumps(self.data))
        if not backfill:
            self._rollback_run(run_date)
        errors, warnings = self.validate_batch(run_date, events)
        if errors:
            self.data = snapshot
            self._cache = {}
            raise ValidationError(errors)

        d = self.data
        d["runs"].append({"run_date": run_date, "window": window or [],
                          "ingested_at": datetime.now(SH_TZ).isoformat(timespec="seconds"),
                          "event_keys": sorted(e["event_key"] for e in events)})
        alias_ids, created, attached, seen_before = {}, [], [], {}

        # 先建全部新命题，NEW:<alias> 才能在同批次内被引用
        for ev in events:
            dec = ev.get("thesis_decision") or {}
            if dec.get("action") == "new":
                nt = dec["new_thesis"]
                tid = self._next_id()
                d["theses"][tid] = {"id": tid, "name": nt["name"], "statement": nt["statement"],
                                    "object": nt["object"], "consequence": nt["consequence"],
                                    "scope_leaves": list(nt["scope_leaves"]),
                                    "change_types": sorted(nt["change_types"]),
                                    "created_in": run_date, "created_by": ev["event_key"],
                                    "revisions": []}
                if nt.get("alias"):
                    alias_ids[nt["alias"]] = tid
                created.append({"event_id": ev["event_id"], "thesis_id": tid, "name": nt["name"]})

        links_by_key = {l["event_key"]: l for l in d["links"]}
        for ev in events:
            k = ev["event_key"]
            stored = d["events"].get(k)
            if stored:
                prior = [r for r in stored["seen_in_runs"] if r < run_date]
                if prior:
                    seen_before[ev["event_id"]] = prior[-1]
            else:
                stored = d["events"][k] = {
                    "title": ev["event_title"], "entity": ev.get("entity", ""),
                    "source": ev["source"], "first_publish": ev["first_publish_shanghai"],
                    "primary_path": ev["primary_path"], "related_domains": ev.get("related_domains", []),
                    "change_types": ev.get("change_types", []), "rating": ev["rating"],
                    "signal": ev.get("signal", ""), "evidence_form": ev["evidence_form"],
                    "seen_in_runs": [], "labels": {}}
            stored["seen_in_runs"] = sorted(set(stored["seen_in_runs"]) | {run_date})
            stored.setdefault("labels", {})[run_date] = ev["event_id"]

            dec = ev.get("thesis_decision") or {}
            action = dec.get("action", "none")
            if action == "none":
                continue          # 已有 link 的事件保持原裁决
            if action == "new":
                tid = next(c["thesis_id"] for c in created if c["event_id"] == ev["event_id"])
            else:
                tid = dec["thesis_id"]
                if tid.startswith(NEW_REF):
                    tid = alias_ids[tid[len(NEW_REF):]]
            relation = dec.get("relation", "supports")
            old = links_by_key.get(k)
            if old and old["thesis_id"] == tid and old["relation"] == relation:
                continue          # 相邻窗口重复出现、裁决相同：不产生新证据
            if old and backfill:
                if old["decided_in"] > run_date:
                    warnings.append(f"{ev['event_id']}: 已在 {old['decided_in']} 裁决为 "
                                    f"{old['thesis_id']}/{old['relation']}，补跑不改写后续裁决")
                    continue
            if old:
                d["links"].remove(old)
            link = {"event_key": k, "thesis_id": tid, "relation": relation,
                    "decided_in": run_date, "rationale": dec.get("rationale", "")}
            d["links"].append(link)
            links_by_key[k] = link
            attached.append({"event_id": ev["event_id"], "thesis_id": tid, "relation": relation})

        self._cache = {}
        result = {"run_date": run_date, "events": len(events), "new_theses": created,
                  "links": attached, "seen_before": seen_before,
                  "warnings": self._rollback_notes + warnings}
        self.save()
        self._log("ingest", run_date=run_date, new=[c["thesis_id"] for c in created],
                  links=len(attached), seen_before=seen_before)
        return result

    # ---------- 显式决策 ----------
    def _decide(self, rec: dict):
        if not self._locked:
            raise RegistryError("写决策必须持锁")
        rec.setdefault("date", self.latest_run() or _today())
        for key in ("source", "target", "thesis_id", "old", "new"):
            if key in rec and rec[key] not in self.data["theses"]:
                raise RegistryError(f"不存在的命题 {rec[key]}")
        if not (rec.get("reason") or "").strip():
            raise RegistryError("决策必须写 reason")
        self.data["decisions"].append(rec)
        self._cache = {}
        if rec["type"] == "revise":
            self.data["theses"][rec["thesis_id"]]["revisions"].append(
                {"date": rec["date"], "statement": rec["new_statement"], "reason": rec["reason"]})
        self.save()
        self._log(rec["type"], **{k: v for k, v in rec.items() if k != "type"})

    def merge(self, source: str, target: str, reason: str):
        if source == target:
            raise RegistryError("不能合并到自身")
        self._decide({"type": "merge", "source": source, "target": target, "reason": reason})

    def retire(self, tid: str, reason: str):
        self._decide({"type": "retire", "thesis_id": tid, "reason": reason})

    def revise(self, tid: str, statement: str, reason: str):
        self._decide({"type": "revise", "thesis_id": tid, "new_statement": statement, "reason": reason})

    def supersede(self, old: str, new: str, reason: str):
        self._decide({"type": "supersede", "old": old, "new": new, "reason": reason})

    # ---------- 报告（第 7 章输入） ----------
    def report(self, run_date: str) -> dict:
        if run_date not in self.run_dates():
            raise RegistryError(f"registry 中没有 run {run_date}（先 ingest）")
        prev = self.previous_run(run_date)
        rows = []
        for tid in self.theses_as_of(run_date):
            after = self.view(tid, run_date)
            before = self.view(tid, prev) if prev and self.data["theses"][tid]["created_in"] <= prev else None
            new_sup = [s for s in after["support"] if s["decided_in"] == run_date]
            new_con = [s for s in after["contradicts"] if s["decided_in"] == run_date]
            changed = before is None or before["state"] != after["state"] \
                or before["confidence"] != after["confidence"]
            if not (new_sup or new_con or changed):
                continue
            convergence = []
            if len({s["entity"] for s in new_sup if s["entity"]}) >= 2:
                convergence.append("本轮收敛")
            if new_sup and any(s["decided_in"] < run_date for s in after["support"]):
                convergence.append("跨时间收敛")
            rows.append({
                "id": tid, "name": after["name"], "statement": after["statement"],
                "type": after["type"], "entities": after["entities"],
                "state_before": before["state"] if before else None, "state": after["state"],
                "state_reason": after["state_reason"],
                "confidence_before": before["confidence"] if before else None,
                "confidence": after["confidence"], "score": after["score"],
                "breakdown": after["breakdown"], "convergence": convergence,
                "new_support": new_sup, "new_contradicts": new_con,
                "core_judgment": after["state"] in RULES["core_judgment_states"]
                and after["confidence"] not in CM["core_judgment_excludes"],
            })
        rows.sort(key=lambda r: (not r["core_judgment"], -r["score"], r["id"]))
        return {"run_date": run_date, "previous_run": prev, "theses": rows,
                "summary": {"touched": len(rows),
                            "core_judgment": sum(r["core_judgment"] for r in rows),
                            "new": sum(r["state_before"] is None for r in rows),
                            "contested": sum(r["state"] == "contested" for r in rows)}}

    def gaps(self, until: str) -> list[str]:
        """首个 run 到 until（不含）之间没有 run 的日期。窗口固定为"昨日 00:00 → 执行时刻"，
        漏跑一天就有一段时间不在任何窗口里，只能补跑。"""
        dates = self.run_dates()
        if not dates:
            return []
        have, out = set(dates), []
        d = date.fromisoformat(dates[0])
        end = date.fromisoformat(until)
        while d < end:
            if d.isoformat() not in have:
                out.append(d.isoformat())
            d += timedelta(days=1)
        return out

    def stats(self) -> dict:
        by_state, by_conf = {}, {}
        for tid in self.data["theses"]:
            v = self.view(tid)
            by_state[v["state"]] = by_state.get(v["state"], 0) + 1
            by_conf[v["confidence"]] = by_conf.get(v["confidence"], 0) + 1
        return {"runs": len(self.data["runs"]), "latest_run": self.latest_run(),
                "events": len(self.data["events"]), "theses": len(self.data["theses"]),
                "links": len(self.data["links"]), "by_state": by_state, "by_confidence": by_conf}


# ====================================================================
def load_events_dir(events_dir: Path) -> list[dict]:
    out = []
    for f in sorted(Path(events_dir).glob("EV-*.json")):
        ev = json.loads(f.read_text(encoding="utf-8"))
        ev.setdefault("event_id", f.stem)
        out.append(ev)
    return out


def _run_date_from_dir(events_dir: Path) -> str | None:
    name = Path(events_dir).name
    return name[len("events_run_"):] if name.startswith("events_run_") else None


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description="Thesis Registry v2")
    ap.add_argument("--state", default="", help="状态目录（默认 $TECH_BRIEFING_STATE 或 ./state）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("candidates", help="为每个事件写入 thesis_candidates")
    c.add_argument("--events-dir", required=True)
    c.add_argument("--run-date", default="")
    i = sub.add_parser("ingest", help="校验裁决并以 run 为单位事务入库")
    i.add_argument("--events-dir", required=True)
    i.add_argument("--run-date", default="")
    i.add_argument("--report", default="", help="collect_report.json，用于记录窗口")
    i.add_argument("--backfill", action="store_true", help="补跑漏掉的较早日期")
    g = sub.add_parser("gaps", help="列出漏跑的窗口日期")
    g.add_argument("--until", required=True, help="本轮 WINDOW_START_DATE（不含）")
    r = sub.add_parser("report", help="第 7 章输入")
    r.add_argument("--run-date", required=True)
    r.add_argument("--out", default="")
    s = sub.add_parser("show")
    s.add_argument("id")
    q = sub.add_parser("search")
    q.add_argument("keyword")
    sub.add_parser("stats")
    m = sub.add_parser("merge")
    m.add_argument("--source", required=True)
    m.add_argument("--target", required=True)
    m.add_argument("--reason", required=True)
    rt = sub.add_parser("retire")
    rt.add_argument("--id", required=True)
    rt.add_argument("--reason", required=True)
    rv = sub.add_parser("revise")
    rv.add_argument("--id", required=True)
    rv.add_argument("--statement", required=True)
    rv.add_argument("--reason", required=True)
    sp = sub.add_parser("supersede")
    sp.add_argument("--old", required=True)
    sp.add_argument("--new", required=True)
    sp.add_argument("--reason", required=True)
    args = ap.parse_args()

    state = Path(args.state) if args.state else None
    try:
        reg = Registry(state)
        if args.cmd == "candidates":
            run_date = args.run_date or _run_date_from_dir(args.events_dir)
            for f in sorted(Path(args.events_dir).glob("EV-*.json")):
                ev = json.loads(f.read_text(encoding="utf-8"))
                ev["thesis_candidates"] = reg.candidates(ev, run_date)
                f.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(f"{f.stem}: {[x['id'] for x in ev['thesis_candidates']]}")
        elif args.cmd == "ingest":
            run_date = args.run_date or _run_date_from_dir(args.events_dir)
            if not run_date:
                raise RegistryError("无法确定 run_date：用 --run-date 指定 WINDOW_START_DATE")
            window = []
            if args.report:
                tw = json.loads(Path(args.report).read_text(encoding="utf-8")).get("target_window", {})
                window = [tw.get("start", ""), tw.get("end", "")]
            with reg:
                res = reg.ingest_run(run_date, load_events_dir(Path(args.events_dir)), window,
                                     backfill=args.backfill)
            _print(res)
        elif args.cmd == "report":
            rep = reg.report(args.run_date)
            if args.out:
                Path(args.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"report → {args.out}（{rep['summary']}）")
            else:
                _print(rep)
        elif args.cmd == "show":
            _print(reg.view(args.id))
        elif args.cmd == "search":
            _print(reg.search(args.keyword))
        elif args.cmd == "gaps":
            missing = reg.gaps(args.until)
            _print({"until": args.until, "missing": missing})
            if missing:
                print(f"漏跑 {len(missing)} 个窗口；每个日期 D 按完整流程补跑："
                      f"collect_sources.py --date <D+1>，ingest --backfill --run-date D", file=sys.stderr)
        elif args.cmd == "stats":
            _print(reg.stats())
        else:
            with reg:
                if args.cmd == "merge":
                    reg.merge(args.source, args.target, args.reason)
                elif args.cmd == "retire":
                    reg.retire(args.id, args.reason)
                elif args.cmd == "revise":
                    reg.revise(args.id, args.statement, args.reason)
                elif args.cmd == "supersede":
                    reg.supersede(args.old, args.new, args.reason)
            print(f"{args.cmd} OK")
        return 0
    except ValidationError as e:
        for err in e.errors:
            print(f"  x {err}")
        print(f"ingest FAIL — {len(e.errors)} 个错误，registry 未改动")
        return 1
    except RegistryError as e:
        print(f"[registry] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
