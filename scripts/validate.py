#!/usr/bin/env python3
"""data/ 以下の検算。おかしな数字がサイトに出る前に止めるためのもの。
失敗すると終了コード1で終わり、ワークフローはコミットせずに止まる。"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# 年金月額の分布: 男女の合計が総数と一致し、公表の合計とも一致すること
pension = load("pension.json")
check(len(pension) == 31, "pension: 階級は31個のはず")
for row in pension:
    check(row["kiso"] == row["kiso_m"] + row["kiso_f"], f"pension: 基礎のみの男女計が不一致 ({row['label']})")
    check(row["kosei"] == row["kosei_m"] + row["kosei_f"], f"pension: 厚生年金の男女計が不一致 ({row['label']})")
# 公表資料(令和6年度末)の合計。年次更新のときは、この2つも新しい資料の合計に書き換える
PUBLISHED_TOTALS = {"kiso": 4_442_745, "kosei": 16_085_696}
for key, total in PUBLISHED_TOTALS.items():
    got = sum(row[key] for row in pension)
    check(got == total, f"pension: {key} の合計 {got:,} が公表値 {total:,} と不一致")

# 生活扶助の例: 常識的な範囲にあること
thresholds = {row["id"]: row["amount"] for row in load("thresholds.json")}
check(set(thresholds) == {"rural", "tokyo"}, "thresholds: rural と tokyo が必要")
check(50_000 < thresholds.get("rural", 0) < thresholds.get("tokyo", 0) < 120_000, "thresholds: 金額が想定範囲外")

# 受給実態: 月次更新される3項目の整合
reach = {row["id"]: row for row in load("reach.json")}
for key in ["elderly_households", "elderly_share", "elderly_single", "pension_rate",
            "applications_2024", "starts_2024", "kyoto_consult", "kyoto_apply",
            "ratio_income", "ratio_asset"]:
    check(key in reach, f"reach: {key} がない")
if not errors:
    hh, single, share = reach["elderly_households"], reach["elderly_single"], reach["elderly_share"]
    check(500_000 <= hh["raw"] <= 1_500_000, f"reach: 高齢者世帯数 {hh['raw']:,} が想定範囲外")
    check(0.7 * hh["raw"] <= single["raw"] <= hh["raw"], "reach: 単身世帯数が高齢者世帯数と整合しない")
    check(40 <= share["raw"] <= 70, f"reach: 高齢者世帯の割合 {share['raw']} が想定範囲外")
    check(abs(hh["value"] - round(hh["raw"] / 1e4, 1)) < 0.05, "reach: 高齢者世帯の表示値が raw と不一致")
    check(abs(single["value"] - round(single["raw"] / 1e4, 1)) < 0.05, "reach: 単身世帯の表示値が raw と不一致")
    check(hh.get("as_of") == single.get("as_of") == share.get("as_of"), "reach: 月次3項目の時点が揃っていない")

# 蓄積テーブル: 列が揃い、同じ指標・地域・時点の重複がなく、最新月がページの数字と一致すること
import csv

with (DATA / "observations.csv").open(encoding="utf-8", newline="") as f:
    obs = list(csv.DictReader(f))
check(bool(obs) and list(obs[0].keys()) == ["indicator", "area", "period", "value", "unit", "source", "fetched_at"], "observations: 列が想定と違う")
for r in obs:
    check(not any(ch in str(val) for val in r.values() for ch in ',"\n'), f"observations: 値にカンマ・引用符・改行を含めない ({r['indicator']} {r['period']})")
keys = [(r["indicator"], r["area"], r["period"]) for r in obs]
check(len(keys) == len(set(keys)), "observations: 同じ指標・地域・時点の行が重複している")
for r in obs:
    try:
        float(r["value"])
    except ValueError:
        check(False, f"observations: 値が数値でない ({r})")
if not errors:
    latest = {}
    for r in obs:
        if r["area"] == "00000" and r["period"] > latest.get(r["indicator"], ("", ""))[0]:
            latest[r["indicator"]] = (r["period"], float(r["value"]))
    pairs = [("hihogo.elderly_households", "elderly_households"), ("hihogo.elderly_share", "elderly_share"),
             ("hihogo.elderly_single_households", "elderly_single")]
    for indicator, rid in pairs:
        period, value = latest.get(indicator, ("", None))
        check(period == reach[rid].get("as_of") and value == reach[rid]["raw"],
              f"observations: {indicator} の最新値がページの数字と一致しない")

# 問いの台帳: 一覧と管理ページの元になる。ページとデータファイルが実在すること
ROOT = DATA.parent
questions = load("questions.json")
check(bool(questions), "questions: 問いが1つもない")
indicators = {r["indicator"] for r in obs}
for q in questions:
    for key in ["id", "title", "summary", "url", "sources"]:
        check(bool(q.get(key)), f"questions: {q.get('id')} に {key} がない")
    check((ROOT / q.get("url", "") / "index.html").is_file(), f"questions: {q.get('url')} のページがない")
    for s in q.get("sources", []):
        for key in ["name", "publisher", "url", "frequency", "method", "data", "file"]:
            check(bool(s.get(key)), f"questions: {q.get('id')} の取得先 {s.get('name')} に {key} がない")
        check(s.get("method") in ("自動", "手動"), f"questions: 取得方法は 自動 か 手動 ({s.get('name')})")
        check((ROOT / s.get("file", "")).is_file(), f"questions: {s.get('file')} がない")
        if s.get("method") == "自動":
            check(s.get("indicator") in indicators, f"questions: 自動取得の指標 {s.get('indicator')} が observations.csv にない")
        else:
            check(bool(s.get("as_of")), f"questions: 手動の取得先 {s.get('name')} に as_of(手元の時点)がない")

if errors:
    print("検算に失敗しました:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("検算OK")
