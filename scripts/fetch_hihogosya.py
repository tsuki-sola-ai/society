#!/usr/bin/env python3
"""厚生労働省「被保護者調査」月次概数のPDFから、高齢者世帯の数字を取り込む。

公表PDFのURLは https://www.mhlw.go.jp/toukei/saikin/hw/hihogosya/m{西暦}/dl/{月2桁}-01.pdf
という規則で並んでいる。新しい月から順に探し、見つかった最新の月を data/reach.json に反映する。
読み取れない、または数字が不自然なときは何も書き換えずに終了コード1で終わる。

取得した値は data/observations.csv にも1行ずつ積み上げる(指標・地域・時点・値・出典)。
こちらは上書きせず履歴として残すので、時系列や他の統計との組み合わせに使える。

  python scripts/fetch_hihogosya.py               # 最新月を取得して反映
  python scripts/fetch_hihogosya.py --backfill 36 # 過去36か月分を遡って蓄積
  python scripts/fetch_hihogosya.py --selftest    # ネットワークなしで解析部分だけ確認
"""
import csv
import datetime
import io
import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
REACH = DATA / "reach.json"
OBS = DATA / "observations.csv"
OBS_FIELDS = ["indicator", "area", "period", "value", "unit", "source", "fetched_at"]
AREA_JAPAN = "00000"  # 全国。都道府県・市区町村は全国地方公共団体コードを使う
URL = "https://www.mhlw.go.jp/toukei/saikin/hw/hihogosya/m{y}/dl/{m:02d}-01.pdf"
NUM = r"([0-9][0-9,]*)"


def parse(text):
    """PDFから抜き出した文字列から、高齢者世帯数・構成割合・うち単身世帯数を読む。"""
    flat = re.sub(r"[ \t　]+", " ", text)
    m = re.search(r"高齢者世帯\s*" + NUM + r"\s*([0-9]+\.[0-9])\s*[%％]", flat)
    if not m:
        raise ValueError("「高齢者世帯」の行が見つからない(PDFの体裁が変わった可能性)")
    households = int(m.group(1).replace(",", ""))
    share = float(m.group(2))
    s = re.search(r"単身世帯\s*" + NUM, flat[m.end():])
    if not s:
        raise ValueError("「単身世帯」の行が見つからない")
    single = int(s.group(1).replace(",", ""))
    if not (500_000 <= households <= 1_500_000):
        raise ValueError(f"高齢者世帯数 {households:,} が想定範囲外")
    if not (40 <= share <= 70):
        raise ValueError(f"構成割合 {share} が想定範囲外")
    if not (0.7 * households <= single <= households):
        raise ValueError(f"単身世帯数 {single:,} が高齢者世帯数と整合しない")
    return households, share, single


def candidates(today, back=8):
    """今月から遡って、公表されていそうな月を新しい順に返す。"""
    y, m = today.year, today.month
    for _ in range(back):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        yield y, m


def fetch_month(y, m):
    """指定した月のPDFを取得して解析する。未公表なら None。"""
    import pdfplumber
    import requests

    url = URL.format(y=y, m=m)
    res = requests.get(url, timeout=60, headers={"User-Agent": "society-data-bot (github.com/tsuki-sola-ai/society)"})
    if res.status_code != 200 or not res.content.startswith(b"%PDF"):
        return None
    with pdfplumber.open(io.BytesIO(res.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:3])
    return url, parse(text)


def fetch_latest():
    for y, m in candidates(datetime.date.today()):
        got = fetch_month(y, m)
        if got is None:
            print(f"{y}-{m:02d}: まだ公表されていない")
            continue
        return y, m, got[0], got[1]
    raise RuntimeError("直近8か月のどの月のPDFも取得できなかった")


def record(y, m, values, url, today=None):
    """observations.csv に積み上げる。同じ指標・地域・時点の行があれば値を置き換える(概数の訂正に追従)。"""
    households, share, single = values
    period = f"{y}-{m:02d}"
    fetched = (today or datetime.date.today()).isoformat()
    new = [
        ("hihogo.elderly_households", households, "世帯"),
        ("hihogo.elderly_share", share, "%"),
        ("hihogo.elderly_single_households", single, "世帯"),
    ]
    rows = []
    if OBS.exists():
        with OBS.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    index = {(r["indicator"], r["area"], r["period"]): r for r in rows}
    changed = False
    for indicator, value, unit in new:
        key = (indicator, AREA_JAPAN, period)
        row = index.get(key)
        if row is None:
            row = dict(indicator=indicator, area=AREA_JAPAN, period=period, value=str(value), unit=unit, source=url, fetched_at=fetched)
            rows.append(row)
            index[key] = row
            changed = True
        elif row["value"] != str(value):
            row.update(value=str(value), source=url, fetched_at=fetched)
            changed = True
    if changed:
        rows.sort(key=lambda r: (r["indicator"], r["area"], r["period"]))
        with OBS.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OBS_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return changed


def backfill(months):
    """過去の月を遡って observations.csv に蓄積する。読めない月は飛ばして報告する。"""
    added = skipped = 0
    for y, m in candidates(datetime.date.today(), back=months):
        try:
            got = fetch_month(y, m)
        except ValueError as e:
            print(f"{y}-{m:02d}: 読み取れず({e})")
            skipped += 1
            continue
        if got is None:
            print(f"{y}-{m:02d}: PDFなし")
            continue
        added += record(y, m, got[1], got[0])
        print(f"{y}-{m:02d}: 高齢者世帯 {got[1][0]:,}")
    print(f"蓄積 {added} か月分を追加・更新、読み取れず {skipped} か月")


def apply(y, m, values):
    households, share, single = values
    as_of = f"{y}-{m:02d}"
    period = f"令和{y - 2018}年{m}月(概数)"
    rows = json.loads(REACH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}
    if (by_id["elderly_households"].get("as_of") or "") > as_of:
        print(f"手元のデータ({by_id['elderly_households']['as_of']})のほうが新しいので何もしない")
        return False
    new = {
        "elderly_households": (round(households / 1e4, 1), households),
        "elderly_share": (share, share),
        "elderly_single": (round(single / 1e4, 1), single),
    }
    changed = False
    for key, (value, raw) in new.items():
        row = by_id[key]
        if (row["value"], row["raw"], row.get("as_of")) != (value, raw, as_of):
            row.update(value=value, raw=raw, as_of=as_of, period=period)
            changed = True
    if changed:
        REACH.write_text("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n", encoding="utf-8")
    return changed


def selftest():
    sample = (
        "３．世帯類型別世帯数及び割合（保護停止中を含まない。）\n"
        "総数 1,635,654 (-3,097) (-0.2%) 1,635,284 (-2,727)\n"
        "構成割合\n"
        "高齢者世帯 900,635 55.2% 902,338 (-1,703) (-0.2%) 903,116 (-2,481)\n"
        "単身世帯 842,484 51.6% 841,679 (805) (0.1%) 844,423 (-1,939)\n"
        "２人以上の世帯 58,151 3.6% 60,659 (-2,508) (-4.1%) 58,693 (-542)\n"
    )
    assert parse(sample) == (900_635, 55.2, 842_484), parse(sample)
    assert parse(sample.replace("%", "％").replace(" ", "　")) == (900_635, 55.2, 842_484)
    for bad in ["高齢者世帯 9,006 55.2%\n単身世帯 8,424", "何もない文書"]:
        try:
            parse(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("不正な入力を通してしまった: " + bad)
    assert list(candidates(datetime.date(2026, 2, 10), 3)) == [(2026, 1), (2025, 12), (2025, 11)]
    # 蓄積: 一時ファイルに対して、追加・重複・訂正の3通りを確かめる
    import tempfile
    global OBS
    keep, OBS = OBS, Path(tempfile.mkdtemp()) / "observations.csv"
    try:
        day = datetime.date(2026, 11, 20)
        assert record(2026, 8, (900_635, 55.2, 842_484), "u1", day) is True
        assert record(2026, 8, (900_635, 55.2, 842_484), "u1", day) is False
        assert record(2026, 7, (901_000, 55.1, 843_000), "u0", day) is True
        assert record(2026, 8, (900_700, 55.2, 842_484), "u2", day) is True
        with OBS.open(encoding="utf-8", newline="") as f:
            got = list(csv.DictReader(f))
        assert len(got) == 6 and [r["period"] for r in got[:2]] == ["2026-07", "2026-08"], got
        assert got[1]["value"] == "900700" and got[1]["source"] == "u2", got[1]
    finally:
        OBS = keep
    print("selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    if "--backfill" in sys.argv:
        backfill(int(sys.argv[sys.argv.index("--backfill") + 1]))
        sys.exit(0)
    try:
        y, m, url, values = fetch_latest()
    except Exception as e:  # 読めなかったら、何も書き換えずに失敗として終わる
        print("取得に失敗:", e)
        sys.exit(1)
    print(f"{y}-{m:02d} を取得: 高齢者世帯 {values[0]:,} / 構成割合 {values[1]}% / 単身 {values[2]:,}  ({url})")
    logged = record(y, m, values, url)
    print("更新あり" if apply(y, m, values) or logged else "変更なし")
