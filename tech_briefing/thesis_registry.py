#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thesis Registry · query / ingest / update API

跨 run 持久化技术命题（thesis）的轻量状态机。
- Upper ontology 从 thesis_ontology.json 读取（稳定骨架）
- Thesis 实例持久化在 thesis_registry.json（跨 run 累积）
- Per-run instances 由 LLM 动态生成，通过 ingest_event 写入

三种核心操作：
  query  — 反向查询历史 thesis，供 P3 聚类收敛判断跨时间收敛
  ingest — 把本轮事件映射/创建 thesis，供 P2 抽象提升后持久化
  update — 运行生命周期迁移（proposed→active / active→dormant / 合并 / 退役）

用法：
  # CLI
  python thesis_registry.py query --track TR-MODEL
  python thesis_registry.py query --search "扩散"
  python thesis_registry.py query --id TH-001
  python thesis_registry.py ingest --event-file /path/to/event.json
  python thesis_registry.py update --run-date 2026-10-20
  python thesis_registry.py stats

  # 作为模块
  from thesis_registry import Registry
  reg = Registry()
  hits = reg.query_by_track("TR-MODEL")
  reg.ingest_event(event_dict, run_date="2026-10-20")
  reg.save()
"""
import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Optional


ASSETS_DIR = Path(__file__).parent                  # assets/ — 只读引擎 + 骨架
SKILL_DIR = ASSETS_DIR.parent                       # tech-briefing/
DATA_DIR = SKILL_DIR / "data"                        # data/ — 可写全局状态
ONTOLOGY_PATH = ASSETS_DIR / "thesis_ontology.json"  # 骨架在 assets/
REGISTRY_PATH = DATA_DIR / "thesis_registry.json"    # 实例库在 data/
DATA_DIR.mkdir(parents=True, exist_ok=True)          # 首次运行时确保 data/ 存在

# 默认生命周期参数
DORMANT_AFTER_RUNS = 14  # 连续 N run 无新证据 → dormant
RETIRE_AFTER_RUNS = 30  # dormant 后再 N run 仍无证据 → retired


def shanghai_today() -> str:
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).strftime("%Y-%m-%d")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class Registry:
    """Thesis registry — 封装 ontology + thesis 实例的查询与写入。"""

    def __init__(self,
                 ontology_path: Path = ONTOLOGY_PATH,
                 registry_path: Path = REGISTRY_PATH):
        self.ontology_path = ontology_path
        self.registry_path = registry_path
        self.ontology = load_json(ontology_path)
        self.registry = load_json(registry_path)
        if "theses" not in self.registry:
            self.registry["theses"] = []

    # ---------- query ----------
    def all_theses(self) -> list[dict]:
        return self.registry.get("theses", [])

    def get_by_id(self, thesis_id: str) -> Optional[dict]:
        for t in self.all_theses():
            if t["id"] == thesis_id:
                return t
        return None

    def query_by_track(self, track_id: str) -> list[dict]:
        return [t for t in self.all_theses() if track_id in t.get("tracks", [])]

    def query_by_section(self, section_id: str) -> list[dict]:
        return [t for t in self.all_theses() if section_id in t.get("sections", [])]

    def query_by_state(self, state: str) -> list[dict]:
        return [t for t in self.all_theses() if t.get("state") == state]

    def query_by_change_type(self, ct_id: str) -> list[dict]:
        return [t for t in self.all_theses() if ct_id in t.get("change_types", [])]

    def query_by_entity(self, entity: str) -> list[dict]:
        hits = []
        for t in self.all_theses():
            if entity in t.get("convergence_entities", []):
                hits.append(t)
            for ev in t.get("events", []):
                if entity.lower() in ev.get("source", "").lower():
                    hits.append(t)
                    break
        return hits

    def search(self, keyword: str) -> list[dict]:
        kw = keyword.lower()
        hits = []
        for t in self.all_theses():
            blob = (t.get("name", "") + " " + t.get("name_en", "") +
                    " " + t.get("statement", "")).lower()
            if kw in blob:
                hits.append(t)
        return hits

    def query_for_convergence(self, event: dict) -> list[dict]:
        """
        P3 聚类收敛时调用：根据事件的 change_types / tracks / sections
        找出可能产生跨时间收敛的历史 thesis。
        返回 active / dormant 的 thesis（排除 retired）。
        """
        ct = event.get("change_types", [])
        tracks = event.get("tracks", [])
        sections = event.get("sections", [])
        hits = []
        for t in self.all_theses():
            if t.get("state") == "retired":
                continue
            overlap_ct = set(ct) & set(t.get("change_types", []))
            overlap_tr = set(tracks) & set(t.get("tracks", []))
            overlap_sec = set(sections) & set(t.get("sections", []))
            if overlap_ct and (overlap_tr or overlap_sec):
                hits.append(t)
        return hits

    # ---------- ingest ----------
    def ingest_event(self, event: dict, run_date: Optional[str] = None) -> dict:
        """
        把一个 P2 抽象提升后的事件写入 registry。

        event 字段：
          thesis_name, thesis_name_en (可选), statement,
          thesis_type (Frontier/Convergence), change_types (CT-xx),
          tracks (TR-xxx), sections (s2-x / s3-x),
          rating (A+/A/B...), signal (Frontier/Convergence/Early),
          first_publish_shanghai, source, event_title, key_data,
          confidence (可选), proposed_thesis_id (可选, 若映射到已有 thesis)

        返回写入的 thesis 字典。
        """
        run_date = run_date or shanghai_today()
        thesis_id = event.get("proposed_thesis_id")
        existing = self.get_by_id(thesis_id) if thesis_id else None

        # 若没有 proposed_thesis_id，尝试用 thesis_name_en 精确匹配已有 thesis
        if not existing and event.get("thesis_name_en"):
            name_en = event["thesis_name_en"]
            for t in self.registry.get("theses", []):
                if t.get("name_en") == name_en and t.get("state") != "merged":
                    existing = t
                    break

        event_record = {
            "brief_date": event.get("brief_date", run_date),
            "event_title": event.get("event_title", ""),
            "first_publish_shanghai": event.get("first_publish_shanghai", ""),
            "rating": event.get("rating", ""),
            "signal": event.get("signal", ""),
            "source": event.get("source", ""),
            "key_data": event.get("key_data", ""),
        }

        if existing:
            # 映射到已有 thesis — 追加事件，更新 last_seen / evidence_count / state
            existing["events"].append(event_record)
            existing["last_seen"] = run_date
            existing["evidence_count"] = existing.get("evidence_count", 0) + 1
            # proposed → active：再次出现即升级
            if existing.get("state") == "proposed":
                existing["state"] = "active"
            # 追加新实体（去重）
            ent = event.get("entity", "")
            if ent and ent not in existing.get("convergence_entities", []):
                existing["convergence_entities"].append(ent)
            # 更新置信度（取更高）
            new_conf = event.get("confidence")
            if new_conf:
                existing["confidence"] = _max_confidence(
                    existing.get("confidence", "Low"), new_conf)
            return existing

        # 创建新 thesis
        new_id = self._next_thesis_id()
        new_thesis = {
            "id": new_id,
            "name": event.get("thesis_name", ""),
            "name_en": event.get("thesis_name_en", ""),
            "thesis_type": event.get("thesis_type", "Frontier Thesis"),
            "statement": event.get("statement", ""),
            "change_types": event.get("change_types", []),
            "tracks": event.get("tracks", []),
            "sections": event.get("sections", []),
            "state": "proposed" if event.get("rating", "B") in ("B", "C") else "active",
            "confidence": event.get("confidence", "Medium"),
            "first_seen": run_date,
            "last_seen": run_date,
            "evidence_count": 1,
            "convergence_entities": [event.get("entity", "")] if event.get("entity") else [],
            "counter_evidence": [],
            "events": [event_record],
            "notes": event.get("notes", ""),
        }
        self.registry["theses"].append(new_thesis)
        return new_thesis

    def _next_thesis_id(self) -> str:
        existing_ids = [t["id"] for t in self.all_theses() if t["id"].startswith("TH-")]
        max_n = 0
        for tid in existing_ids:
            try:
                n = int(tid.split("-")[1])
                if n > max_n:
                    max_n = n
            except (ValueError, IndexError):
                continue
        return f"TH-{max_n + 1:03d}"

    # ---------- update / lifecycle ----------
    def run_lifecycle(self, run_date: Optional[str] = None) -> dict:
        """
        每次 run 结束后调用：根据 last_seen 与 run_date 的差值
        执行状态迁移。

        返回迁移摘要 {state_changes: [...], merges: [...]}。
        """
        run_date = run_date or shanghai_today()
        changes = []
        for t in self.all_theses():
            old_state = t.get("state", "active")
            days_since = _days_between(t.get("last_seen", run_date), run_date)
            # 粗略按"每轮 run 间隔 1 天"估算 run 数
            runs_since = max(0, days_since)

            if old_state == "active" and runs_since >= DORMANT_AFTER_RUNS:
                t["state"] = "dormant"
                changes.append({"id": t["id"], "from": old_state, "to": "dormant"})
            elif old_state == "dormant" and runs_since >= DORMANT_AFTER_RUNS + RETIRE_AFTER_RUNS:
                t["state"] = "retired"
                changes.append({"id": t["id"], "from": old_state, "to": "retired"})

        self.registry["last_updated"] = run_date
        return {"state_changes": changes}

    def merge_theses(self, source_id: str, target_id: str, run_date: Optional[str] = None) -> dict:
        """把 source thesis 合并到 target，source 标记为 merged。"""
        run_date = run_date or shanghai_today()
        source = self.get_by_id(source_id)
        target = self.get_by_id(target_id)
        if not source or not target:
            raise ValueError(f"merge: thesis not found ({source_id} / {target_id})")
        target["events"].extend(source.get("events", []))
        target["evidence_count"] = target.get("evidence_count", 0) + source.get("evidence_count", 0)
        for ent in source.get("convergence_entities", []):
            if ent not in target.get("convergence_entities", []):
                target["convergence_entities"].append(ent)
        target["last_seen"] = max(target.get("last_seen", run_date),
                                  source.get("last_seen", run_date))
        source["state"] = "merged"
        source["merged_into"] = target_id
        return {"merged": source_id, "into": target_id}

    def add_counter_evidence(self, thesis_id: str, evidence: str, run_date: Optional[str] = None) -> dict:
        run_date = run_date or shanghai_today()
        t = self.get_by_id(thesis_id)
        if not t:
            raise ValueError(f"counter-evidence: thesis {thesis_id} not found")
        t.setdefault("counter_evidence", []).append({
            "date": run_date,
            "evidence": evidence,
        })
        return t

    # ---------- stats ----------
    def stats(self) -> dict:
        theses = self.all_theses()
        by_state = {}
        by_track = {}
        by_type = {}
        for t in theses:
            by_state[t.get("state", "unknown")] = by_state.get(t.get("state", "unknown"), 0) + 1
            for tr in t.get("tracks", []):
                by_track[tr] = by_track.get(tr, 0) + 1
            tt = t.get("thesis_type", "unknown")
            by_type[tt] = by_type.get(tt, 0) + 1
        return {
            "total": len(theses),
            "by_state": by_state,
            "by_track": by_track,
            "by_type": by_type,
            "last_updated": self.registry.get("last_updated", ""),
        }

    # ---------- persistence ----------
    def save(self):
        self.registry["last_updated"] = shanghai_today()
        self.registry_path.write_text(
            json.dumps(self.registry, ensure_ascii=False, indent=2),
            encoding="utf-8")


def _max_confidence(a: str, b: str) -> str:
    order = ["Low", "Low-Medium", "Medium", "Medium-High", "High"]
    ia = order.index(a) if a in order else 1
    ib = order.index(b) if b in order else 1
    return order[max(ia, ib)]


def _days_between(d1: str, d2: str) -> int:
    try:
        date1 = datetime.datetime.strptime(d1, "%Y-%m-%d").date()
        date2 = datetime.datetime.strptime(d2, "%Y-%m-%d").date()
        return abs((date2 - date1).days)
    except ValueError:
        return 0


# ---------- CLI ----------
def cmd_query(args, reg: Registry):
    if args.id:
        result = reg.get_by_id(args.id)
        results = [result] if result else []
    elif args.track:
        results = reg.query_by_track(args.track)
    elif args.section:
        results = reg.query_by_section(args.section)
    elif args.state:
        results = reg.query_by_state(args.state)
    elif args.change_type:
        results = reg.query_by_change_type(args.change_type)
    elif args.entity:
        results = reg.query_by_entity(args.entity)
    elif args.search:
        results = reg.search(args.search)
    else:
        results = reg.all_theses()

    print(json.dumps(results, ensure_ascii=False, indent=2))


def cmd_ingest(args, reg: Registry):
    event = load_json(Path(args.event_file))
    t = reg.ingest_event(event, run_date=args.run_date)
    reg.save()
    print(f"[ingest] thesis {t['id']} ({t.get('state')}) — {t['name']}")


def cmd_update(args, reg: Registry):
    result = reg.run_lifecycle(run_date=args.run_date)
    reg.save()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_merge(args, reg: Registry):
    result = reg.merge_theses(args.source, args.target, run_date=args.run_date)
    reg.save()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_stats(args, reg: Registry):
    print(json.dumps(reg.stats(), ensure_ascii=False, indent=2))


def cmd_convergence(args, reg: Registry):
    """读一个 event JSON，输出可能与之跨时间收敛的历史 thesis。"""
    event = load_json(Path(args.event_file))
    hits = reg.query_for_convergence(event)
    print(json.dumps(hits, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Thesis Registry · query / ingest / update")
    sub = parser.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("query", help="查询 thesis")
    q.add_argument("--id")
    q.add_argument("--track")
    q.add_argument("--section")
    q.add_argument("--state")
    q.add_argument("--change-type")
    q.add_argument("--entity")
    q.add_argument("--search")

    ing = sub.add_parser("ingest", help="写入一个事件（创建或更新 thesis）")
    ing.add_argument("--event-file", required=True, help="event JSON 路径")
    ing.add_argument("--run-date", default=shanghai_today())

    upd = sub.add_parser("update", help="运行生命周期迁移")
    upd.add_argument("--run-date", default=shanghai_today())

    mrg = sub.add_parser("merge", help="合并 thesis")
    mrg.add_argument("--source", required=True)
    mrg.add_argument("--target", required=True)
    mrg.add_argument("--run-date", default=shanghai_today())

    sub.add_parser("stats", help="registry 统计")

    cvg = sub.add_parser("convergence", help="查询与某事件可能收敛的历史 thesis")
    cvg.add_argument("--event-file", required=True)

    args = parser.parse_args()
    reg = Registry()

    if args.cmd == "query":
        cmd_query(args, reg)
    elif args.cmd == "ingest":
        cmd_ingest(args, reg)
    elif args.cmd == "update":
        cmd_update(args, reg)
    elif args.cmd == "merge":
        cmd_merge(args, reg)
    elif args.cmd == "stats":
        cmd_stats(args, reg)
    elif args.cmd == "convergence":
        cmd_convergence(args, reg)


if __name__ == "__main__":
    main()
