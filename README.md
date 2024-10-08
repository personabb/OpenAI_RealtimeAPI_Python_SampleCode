

# OpenAI_RealtimeAPI_Python_SampleCode
 OpenAIのRealTimeAPIをpythonで利用するサンプルコードです（非公式）

 Azule版のRealtime APIには対応していません。ご了承ください。

 記事も記載しておりますので、詳しくはそちらをご覧ください。

 https://zenn.dev/asap/articles/4368fd306b592a

ユーザ割り込みも実装しました（main_with_CutIn.py）

 https://zenn.dev/asap/articles/563500af4649da

過去の会話履歴を自動的に削除する機能を追加したサンプルコードもも追加しました。（main_with_CutIn_HistryDelete.py）

https://zenn.dev/asap/articles/af07fcedbbef61
 

## 実行方法

```
pip install websockets　soundfile　numpy　pyaudio
```
```
python main.py
```
 or
 ```
main_with_CutIn.py
```
 or
main_with_CutIn_HistryDelete.py
```

## 記事からの更新

記事ではサンプルコードとして紹介しているため、余分なコードは入れないようにしています。

ここのリポジトリは、自分用に少しだけ改造しているので、その差分を記載します。

1. ユーザ発話の文字起こし情報と、RateLimitの情報を表示するようにしました。

ユーザ発話の文字起こしも取得できるとのことでしたので、それを取得・表示できるように少し変更しています。

ユーザの文字起こしに関しては、なぜかAIの発話の文字起こし（ストリーム）よりも後に表示されるため、表示順が逆になってしまうことが残念です。

stream_audio_and_receive_response関数
```
# 初期リクエスト (モダリティ設定)
init_request = {
    "type": "response.create",
    "response": {
        "modalities": ["audio", "text"],
        "instructions": "関西弁で回答してください。",
        "voice": "echo" #"alloy", "echo", "shimmer"
    }
}

await websocket.send(json.dumps(init_request))

#ユーザ発話の文字認識を有効にする場合は下記が必要
update_request = {
    "type": "session.update",
    "session": {
        "input_audio_transcription":{
            "model": "whisper-1"
        }
    }
}
await websocket.send(json.dumps(update_request))
```

receive_audio関数
```
#ユーザ発話の文字起こしを出力
elif "type" in response_data and response_data["type"] == "conversation.item.input_audio_transcription.completed":
    print("\n↪︎by user messages: ", response_data["transcript"])
# レートリミットの情報を取得
elif "type" in response_data and response_data["type"] == "rate_limits.updated":
    if response_data["rate_limits"][0]["remaining"] == 0:
        print(f"Rate limits: {response_data['rate_limits'][0]['remaining']} requests remaining.")
```
