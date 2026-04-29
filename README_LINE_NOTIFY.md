# 勝負レース LINE通知 追加ファイル

## 追加するファイル

このフォルダの以下を、既存の地方版アプリと同じフォルダにコピーしてください。

- `line_client.py`
- `notify_db.py`
- `shobu_engine.py`
- `notify_local.py`

既存ファイルは基本そのままでOKです。

## LINE側で必要な環境変数

LINE Notifyは終了済みなので、LINE Messaging APIを使います。

```bash
export LINE_CHANNEL_ACCESS_TOKEN="あなたのチャネルアクセストークン"
export LINE_USER_ID="通知先のユーザーID"
```

Windows PowerShellなら:

```powershell
$env:LINE_CHANNEL_ACCESS_TOKEN="あなたのチャネルアクセストークン"
$env:LINE_USER_ID="通知先のユーザーID"
```

## テスト実行

LINE送信せず、通知内容だけ確認:

```bash
python notify_local.py --date 20260429 --places 44,50,54 --races 9,10,11 --budget 3000 --dry-run
```

本送信:

```bash
python notify_local.py --date 20260429 --places 44,50,54 --races 9,10,11 --budget 3000
```

軽め勝負も通知したい場合:

```bash
python notify_local.py --places 44,50,54 --races 1-12 --include-light
```

## cron例

地方を毎日10分おきに確認:

```cron
*/10 * * * * cd /home/keiba/local && /usr/bin/python3 notify_local.py --places 44,50,54 --races 1-12 >> logs/notify_local.log 2>&1
```

最初から全地方場を回すのは重いです。`--places all` は動作確認後にしてください。

## 注意

- デフォルトでは「勝負レース」だけ通知します。
- `--include-light` を付けると「軽め勝負」も通知します。
- 同じ race_id / mode / 軸馬 は `notified.sqlite3` で二重通知防止します。
- 発走時刻を拾えた場合は発走15〜60分前だけ通知します。拾えない場合は判定対象になります。
