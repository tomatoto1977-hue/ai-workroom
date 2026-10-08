# ACE-Step 1.5 音楽生成連携

Video Factory v15 から、ローカルで動く ACE-Step 1.5 を音楽生成プロバイダーとして利用できます。

## できること

- ロック / レゲエ / ポップ / ヒップホップ / EDM / アコースティックを選択
- 日本語歌詞を渡して日本語ボーカル曲を生成
- BPM と曲の長さを指定
- 30秒程度のショート動画用音源を生成
- 生成音源を Video Factory のQAへ渡す
- 自動投稿はしない
- 外部課金サービスを呼ばない

ACE-Step 1.5 は MIT ライセンスのオープンソースプロジェクトで、公式APIはローカルHTTPサーバーとして
`/release_task` → `/query_result` → `/v1/audio` の順に利用できます。

## ローカル起動

ACE-Step 1.5 側でAPIサーバーを起動します。標準例では `http://127.0.0.1:8001` を使用します。

Video Factory側は `video_factory.music.ace_step_music.AceStepMusicProvider` を呼び出します。

## 例

```python
from pathlib import Path
from video_factory.music.ace_step_music import AceStepConfig, AceStepMusicProvider

provider = AceStepMusicProvider(AceStepConfig())

provider.generate(
    lyrics="[Verse]\n今日からひとつ見直そう\n[Chorus]\nその節約、逆に損してない？",
    output_path=Path("outputs/music_rock.wav"),
    genre="rock",
    duration_s=30,
    mood="strong hook, memorable chorus",
)
```

レゲエなら `genre="reggae"` に変更します。

## 安全方針

ACE-Step はローカル生成を前提にし、Video Factory の `auto_publish=False`、
`external_operations=False`、`paid_operations=False` を維持します。

生成物は必ず人間確認を通してから公開します。


## 外部音源の取り込み

MusicSeed / BandLab / GarageBand などでユーザーが作成・書き出しした音源は、Video Factory に「外部音源」として取り込めます。

対応形式: WAV / MP3 / M4A / AAC / FLAC / OGG

Video Factory は MusicSeed / BandLab / GarageBand へ自動ログインしたり、課金操作・公開操作を行いません。音源ファイルをユーザーが用意し、人間確認を経て動画へ組み込みます。

### 推奨の使い分け

- ACE-Step local: 自動化・日本語ボーカル・ロック/レゲエ等の生成
- MusicSeed: 歌入り曲の試作。無料枠は商用利用条件に注意
- BandLab: 無料の作曲・編集・書き出し
- GarageBand: iPhoneでの手直し・仕上げ
- none: 音楽なし

外部音源は「生成エンジン」ではなく「取り込み経路」として扱うため、Video Factory の安全ゲートを維持したまま利用できます。
