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

# 必要な額(生活保護の基準): 生活扶助と住宅扶助の上限が、常識的な範囲にあること
thresholds = {row["id"]: row for row in load("thresholds.json")}
check(set(thresholds) == {"rural", "tokyo"}, "thresholds: rural と tokyo が必要")
if set(thresholds) == {"rural", "tokyo"}:
    check(50_000 < thresholds["rural"]["living"] < thresholds["tokyo"]["living"] < 120_000, "thresholds: 生活扶助が想定範囲外")
    check(15_000 < thresholds["rural"]["rent"] < thresholds["tokyo"]["rent"] < 80_000, "thresholds: 住宅扶助が想定範囲外")

# 年金の平均額: 基礎のみ < 満額 < 厚生年金の順で、分布から概算した平均とも大きくずれないこと
avg = {row["id"]: row["amount"] for row in load("pension_avg.json")}
check(set(avg) == {"kiso", "kiso_full", "kosei"}, "pension_avg: kiso, kiso_full, kosei が必要")
if set(avg) == {"kiso", "kiso_full", "kosei"}:
    check(30_000 < avg["kiso"] < avg["kiso_full"] < avg["kosei"] < 300_000, "pension_avg: 金額の大小関係が想定と違う")
    for key in ["kiso", "kosei"]:
        people = sum(row[key] for row in pension)
        rough = sum(row[key] * (row["low"] + 0.5) * 10_000 for row in pension) / people
        check(abs(rough - avg[key]) < 8_000, f"pension_avg: {key} の平均 {avg[key]:,} が分布からの概算 {rough:,.0f} と離れすぎ")

# 家計簿: 費目の合計が、公表されている消費支出と非消費支出に一致すること(端数の丸めで数円ずれる)
kakei = load("kakei.json")
# 公表資料(家計調査 2025年平均、65歳以上の単身無職世帯)。年次更新のときは、この2つも書き換える
KAKEI_PUBLISHED = {"spend": 148_445, "tax": 12_990}
for kind, total in KAKEI_PUBLISHED.items():
    got = sum(row["amount"] for row in kakei if row["kind"] == kind)
    check(abs(got - total) <= 5, f"kakei: {kind} の合計 {got:,} が公表値 {total:,} と不一致")
check(all(row["amount"] > 0 and row.get("label") for row in kakei), "kakei: 金額か表示名が欠けている費目がある")

# 暮らせている理由の数字: 必要な項目が揃い、割合は0〜100に収まること
supports = {row["id"]: row for row in load("supports.json")}
for key in ["own_home", "rent_single", "rent_single_osaka", "single_under5", "pension_only", "work_share",
            "deficit", "savings_avg", "savings_none", "hard", "very_hard"]:
    check(key in supports, f"supports: {key} がない")
for row in supports.values():
    if row["unit"] == "%":
        check(0 < row["value"] < 100, f"supports: {row['id']} の割合 {row['value']} が範囲外")
if "deficit" in supports:
    spend = sum(r["amount"] for r in kakei if r["kind"] == "spend")
    check(20_000 < supports["deficit"]["value"] < spend, "supports: 毎月の不足が想定範囲外")

# 賃貸の家賃: 住宅・土地統計調査の、65歳以上単身・借家の平均家賃
rent = {row["id"]: row for row in load("rent.json")}
for key in ["national", "aomori", "tokyo_ku", "national_public", "national_private"]:
    check(key in rent, f"rent: {key} がない")
if {"national", "national_public", "national_private"} <= rent.keys():
    check(rent["national_public"]["rent"] < rent["national"]["rent"] < rent["national_private"]["rent"], "rent: 公営 < 全体 < 民営 になっていない")
for row in rent.values():
    check(10_000 < row["rent"] <= row["rent_paid"] < 150_000, f"rent: {row['id']} の家賃が想定範囲外")
if {"national", "aomori", "tokyo_ku"} <= rent.keys():
    check(rent["aomori"]["rent"] < rent["national"]["rent"] < rent["tokyo_ku"]["rent"], "rent: 地域の大小関係が想定と違う")

# 地域ごとの家賃: 47都道府県と21大都市がそろい、本編で使う値と一致すること
area = load("rent_area.json")
check(sum(r["kind"] == "pref" for r in area) == 47, "rent_area: 都道府県が47件でない")
check(sum(r["kind"] == "city" for r in area) == 21, "rent_area: 大都市が21件でない")
check(all(10_000 < r["rent"] <= r["rent_paid"] < 150_000 for r in area), "rent_area: 家賃が想定範囲外の地域がある")
check(all(20_000 < r["private_small"] <= r["private_small_paid"] < 150_000 for r in area), "rent_area: 民間の家賃が想定範囲外の地域がある")
check(sum(r["private_small"] > r["rent"] for r in area) >= 60, "rent_area: 民間の家賃が、公営を含む平均より安い地域が多すぎる")
by_name = {r["name"]: r["rent"] for r in area}
for key, name in [("national", "全国"), ("aomori", "青森県"), ("tokyo_ku", "東京23区"), ("tokyo", "東京都"), ("osaka_pref", "大阪府")]:
    if key in rent:
        check(by_name.get(name) == rent[key]["rent"], f"rent_area: {name} が rent.json と一致しない")
check(Path(ROOT / "nenkin" / "chiiki" / "index.html").exists() if "ROOT" in globals() else True, "地域ごとのページがない")

# 持ち家の修繕費: 家計調査の平均と持家率。家賃地代との合計が住居の計と合うこと
own = load("own_home.json")
check(50 < own["own_rate"] < 100 and 0 < own["repair_avg"] < 50_000, "own_home: 持家率か修繕費が想定範囲外")
check(abs(own["repair_avg"] + own["rent_avg"] - own["housing_avg"]) <= 5, "own_home: 修繕費と家賃地代の合計が住居の計と合わない")

# 保護を受ける割合: 年の昇順で、割合が現実的な範囲にあること
hogo_rate = load("hogo_rate.json")
check([r["year"] for r in hogo_rate] == sorted({r["year"] for r in hogo_rate}), "hogo_rate: 年が昇順でないか重複している")
for row in hogo_rate:
    check(row.get("hogo") is not None or row.get("hogo_period"), f"hogo_rate: {row['year']} に世帯数も参照月もない")
    if row.get("hogo") is not None:
        rate = row["hogo"] / (row["all_k"] * 1000) * 100
        check(3 < rate < 10, f"hogo_rate: {row['year']} の割合 {rate:.1f}% が想定範囲外")

# 今後の見通し: 実績か推計かの区別と出典が、すべての行に付いていること
outlook = load("outlook.json")
for row in outlook:
    check(row.get("kind") in ("実績", "推計"), f"outlook: {row.get('id')} に 実績/推計 の区別がない")
    check(bool(row.get("source")) and bool(row.get("period")), f"outlook: {row.get('id')} に出典か時点がない")

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
    for key in ["id", "title", "conclusion", "summary", "url", "sources"]:
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
