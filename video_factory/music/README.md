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
