# society

公的統計を、暮らしの実感に引き寄せて見るためのサイトです。

公開ページ: https://tsuki-sola-ai.github.io/society/

## いまあるもの

- **問いの一覧** (`index.html`): トップページ。問いを並べた目次
- **年金だけで暮らせるのか** (`nenkin/`): 年金月額の分布に生活扶助の目安を重ね、生活保護が実際に届いているかを数字で見る
- **データの管理状況** (`kanri/`): 問いごとの取得先、頻度、取得方法、主なデータ、手元の最新時点の一覧

## 構成

| 場所 | 中身 |
|---|---|
| `index.html` | 問いの一覧。`data/questions.json` を読んで並べる |
| `nenkin/index.html` | 問いのページ。ビルド不要の静的HTMLで、`data/` を読んで描画する |
| `kanri/index.html` | 管理用の一覧。`data/questions.json` と `data/observations.csv` から作る |
| `assets/base.css` | 一覧と管理ページの共通スタイル |
| `assets/views.js` | 閲覧数の表示。集計は GoatCounter(クッキーなし)。管理ページは計測していない |
| `data/questions.json` | 問いの台帳。問いごとの取得先、頻度、取得方法、主なデータ |
| `data/pension.json` | 年金月額階級別の受給権者数(年1回、手動更新) |
| `data/thresholds.json` | 必要な額の元になる生活保護の基準(生活扶助の例と住宅扶助の上限。制度改定時に手動更新) |
| `data/kakei.json` | 家計簿の費目と金額(家計調査の65歳以上単身無職世帯。年1回、手動更新) |
| `data/supports.json` | 年金が少なくても暮らせている理由の数字(持ち家、所得の内訳、貯蓄、生活意識。手動更新) |
| `data/outlook.json` | 今後の見通し(国の機関による将来推計。実績と推計の区別つき) |
| `data/pension_avg.json` | 年金の平均額と基礎年金の満額(年1回、手動更新) |
| `data/reach.json` | 受給実態の数字。高齢者世帯の3項目だけ毎月自動更新 |
| `data/observations.csv` | 蓄積用のテーブル。取得した値を上書きせず1行ずつ積み上げる |
| `scripts/fetch_hihogosya.py` | 被保護者調査の月次PDFから高齢者世帯の数字を取り込む |
| `scripts/validate.py` | 検算。通らないデータは反映しない |
| `.github/workflows/update-data.yml` | 毎月8日に取得→検算→コミット。手動実行もできる |

## ページの型

問いのページは、どれも次の順で書きます。

1. **問い**: 普通の人が口にする疑問の形で
2. **結論(簡潔に)**: 数行で答えを言い切る
3. **公開情報の分析**: 結論の根拠を、統計ごとに順に示す
4. **結論(詳細) → 対策**: 分析を踏まえた結論と、分からなかったこと
5. **参考: 今後の見通し**(あれば): 将来の推計。現在の統計に基づく結論とは分けて、結論の下に置く
6. **出典**

## 問いを足すとき

1. `新しいフォルダ/index.html` に問いのページを作る
2. `data/questions.json` に、問い、簡潔な結論、取得先を1件足す
3. 一覧と管理ページには自動で載る。`scripts/validate.py` が台帳の抜けを検査する

## データの更新

| データ | 頻度 | 方法 |
|---|---|---|
| 被保護者調査(高齢者世帯数・割合・単身) | 毎月 | 自動 |
| 年金月額の分布と平均額 | 年1回(12月ごろ公表) | 手動。`pension.json`、`pension_avg.json` と `validate.py` の `PUBLISHED_TOTALS` を新しい資料に合わせる |
| 生活扶助の例と住宅扶助の上限 | 制度改定時 | 手動 |
| 家計簿(家計調査) | 年1回(2月ごろ公表) | 手動。`kakei.json` と `validate.py` の `KAKEI_PUBLISHED` を新しい資料に合わせる |
| 推計や事例の数字 | 新しい資料が出たとき | 手動 |

自動更新は、PDFの体裁が変わって読めなくなったときや数字が不自然なときには、何も書き換えずに失敗します。
失敗するとGitHubから通知メールが届き、サイトには前回のデータが残ります。

手元で試すとき:

```
pip install requests pdfplumber
python scripts/fetch_hihogosya.py --selftest   # 解析部分だけ確認
python scripts/fetch_hihogosya.py              # 実際に取得
python scripts/validate.py
python -m http.server                          # http://localhost:8000 で表示
```

## 蓄積用のテーブル

`data/observations.csv` は、あとで他の統計と組み合わせるための土台です。1行が1つの観測値です。

| 列 | 中身 | 例 |
|---|---|---|
| `indicator` | 指標ID。`統計名.項目名` | `hihogo.elderly_households` |
| `area` | 地域コード。全国は `00000`、それ以外は全国地方公共団体コード | `00000` |
| `period` | 時点。月次は `YYYY-MM`、年次は `YYYY`、年度は `FYYYYY` | `2026-08` |
| `value` | 値 | `900635` |
| `unit` | 単位 | `世帯` |
| `source` | 出典のURL | |
| `fetched_at` | 取得日 | `2026-11-20` |

新しい統計を足すときも、この形に揃えて行を足します。指標・地域・時点の3つが共通の鍵になるので、
SQLiteやDuckDBにそのまま読み込んで結合できます。

```
sqlite3 society.db ".import --csv data/observations.csv observations"
```

過去分は、Actionsの「データ更新」を手動実行するときに `backfill` に月数を入れると遡って蓄積できます。

## 数字の扱い

- 出典はページ下部に明記しています。二次情報で確認した数字は、その旨を書いています。
- 数字の誤りに気づいた方は、Issueでお知らせください。
