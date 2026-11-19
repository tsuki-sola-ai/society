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
| `data/thresholds.json` | 生活扶助基準額の例(制度改定時に手動更新) |
| `data/reach.json` | 受給実態の数字。高齢者世帯の3項目だけ毎月自動更新 |
| `data/observations.csv` | 蓄積用のテーブル。取得した値を上書きせず1行ずつ積み上げる |
| `scripts/fetch_hihogosya.py` | 被保護者調査の月次PDFから高齢者世帯の数字を取り込む |
| `scripts/validate.py` | 検算。通らないデータは反映しない |
| `.github/workflows/update-data.yml` | 毎月8日に取得→検算→コミット。手動実行もできる |

## 問いを足すとき

1. `新しいフォルダ/index.html` に問いのページを作る
2. `data/questions.json` に、問いと取得先を1件足す
3. 一覧と管理ページには自動で載る。`scripts/validate.py` が台帳の抜けを検査する

## データの更新

| データ | 頻度 | 方法 |
|---|---|---|
| 被保護者調査(高齢者世帯数・割合・単身) | 毎月 | 自動 |
| 年金月額の分布 | 年1回(12月ごろ公表) | 手動。`pension.json` と `validate.py` の `PUBLISHED_TOTALS` を新しい資料に合わせる |
| 生活扶助の例 | 制度改定時 | 手動 |
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
