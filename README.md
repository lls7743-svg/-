# 前日比下落銘柄スクリーナー

毎朝 9:00〜9:15 JST(東証寄り付き直後)の時間帯に、監視銘柄の中から前日終値比で
一定割合(デフォルト 5%)以上下落した銘柄を検出し、該当銘柄について

- 5分足のローソク足チャート
- 直近30日分の日足ローソク足チャート

を生成するツールです。

## 仕組み

- 株価データは [yfinance](https://github.com/ranaroussi/yfinance)(Yahoo Finance)から無料取得します。
- 監視対象銘柄は `config/tickers.csv` に証券コードと銘柄名を記載します。デフォルトでは
  主要な大型株(約120銘柄)を同梱していますが、**東証プライム全銘柄や日経225の公式構成銘柄
  リストではありません**。必要に応じて自由に追加・編集してください。
- GitHub Actions (`.github/workflows/daily-screener.yml`) が平日 9:00 JST (0:00 UTC) に
  自動実行し、結果を workflow の Artifact としてアップロードします(30日間保存)。
  `workflow_dispatch` から手動実行して閾値を指定することもできます。

## セットアップ

```bash
pip install -r requirements.txt
```

## 使い方

```bash
# デフォルト設定(5%下落、config/tickers.csv を使用)で実行
python src/screener.py

# 閾値を変更
python src/screener.py --threshold 3

# 独自のウォッチリストを使用
python src/screener.py --tickers-file path/to/your_tickers.csv

# チャート生成をスキップしてスクリーニング結果のみ確認
python src/screener.py --no-charts
```

実行すると `output/YYYY-MM-DD/` 以下に以下のファイルが生成されます。

- `report.md` — 該当銘柄の一覧(証券コード・銘柄名・前日終値・現在値・前日比)
- `<コード>.T_5m.png` — 5分足チャート
- `<コード>.T_daily30.png` — 30日分の日足チャート

## ウォッチリストのカスタマイズ

`config/tickers.csv` は `code,name` の2列 CSV です。証券コードは4桁のまま
(例: `7203`)記載すれば自動的に Yahoo Finance 用のティッカー(`7203.T`)に変換されます。
海外銘柄など `.T` 以外のサフィックスが必要な場合はコード欄にサフィックス込みで
記載してください(例: `AAPL.US`)。

## テスト

ネットワークアクセスなしで判定ロジックを検証できるユニットテストを用意しています。

```bash
pip install -r requirements-dev.txt
pytest
```

## 注意事項

- 9:00〜9:15 JST の時間帯は寄り付き直後で株価が大きく変動しやすく、5分足データの
  取得タイミングによって判定結果が多少前後する可能性があります。
- Yahoo Finance の非公式データソースを利用しているため、大量アクセス時のレート制限や
  一時的な欠損が発生する場合があります。
- 本ツールは情報提供のみを目的としており、投資判断は自己責任で行ってください。
