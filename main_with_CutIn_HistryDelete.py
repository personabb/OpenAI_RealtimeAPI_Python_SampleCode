import asyncio
import websockets
import pyaudio
import numpy as np
import base64
import json
import queue
import threading
import os
import time

API_KEY = os.environ.get('OPENAI_API_KEY')

# WebSocket URLとヘッダー情報
# OpenAI
WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
HEADERS = {
    "Authorization": "Bearer " + API_KEY,
    "OpenAI-Beta": "realtime=v1"
}

# キューを初期化
audio_send_queue = queue.Queue()
audio_receive_queue = queue.Queue()

#会話履歴IDリストの初期化
conversation_history_id_Queue = queue.Queue()

# PCM16形式に変換する関数
def base64_to_pcm16(base64_audio):
    audio_data = base64.b64decode(base64_audio)
    return audio_data

# 音声を送信する非同期関数
async def send_audio_from_queue(websocket):
    while True:
        audio_data = await asyncio.get_event_loop().run_in_executor(None, audio_send_queue.get)
        if audio_data is None:
            continue
        
        # PCM16データをBase64にエンコード
        base64_audio = base64.b64encode(audio_data).decode("utf-8")

        audio_event = {
            "type": "input_audio_buffer.append",
            "audio": base64_audio
        }

        # WebSocketで音声データを送信
        await websocket.send(json.dumps(audio_event))

        # キューの処理間隔を少し空ける
        await asyncio.sleep(0)

# マイクからの音声を取得しキューに入れる関数
def read_audio_to_queue(stream, CHUNK):
    while True:
        try:
            audio_data = stream.read(CHUNK, exception_on_overflow=False)
            audio_send_queue.put(audio_data)
        except Exception as e:
            print(f"音声読み取りエラー: {e}")
            break

# サーバーから音声を受信してキューに格納する非同期関数
async def receive_audio_to_queue(websocket):
    print("assistant: ", end = "", flush = True)
    while True:
        response = await websocket.recv()
        if response:
            response_data = json.loads(response)

            # 会話履歴IDをキューに格納
            if "type" in response_data and response_data["type"] == "conversation.item.created":
                conversation_history_id_Queue.put(response_data['item']['id'])
            
            # 会話履歴IDが5以上ある場合、最も古い会話履歴IDを取得し、削除する
            if conversation_history_id_Queue.qsize() >= 5:
                item_id = conversation_history_id_Queue.get()

                delite_event = {
                    "type": "conversation.item.delete",
                    "item_id": item_id
                }

                # WebSocketで音声データを送信
                await websocket.send(json.dumps(delite_event))
                print(f"conversation_history_id: {item_id}を削除しました。")

            # サーバーからの応答をリアルタイムに表示
            if "type" in response_data and response_data["type"] == "response.audio_transcript.delta":
                print(response_data["delta"], end = "", flush = True)
            # サーバからの応答が完了したことを取得
            elif "type" in response_data and response_data["type"] == "response.audio_transcript.done":
                print("\nassistant: ", end = "", flush = True)
            # ユーザ発話の文字起こしを出力
            elif "type" in response_data and response_data["type"] == "conversation.item.input_audio_transcription.completed":
                print("\n↪︎by user messages: ", response_data["transcript"])
            # レートリミットの情報を取得
            elif "type" in response_data and response_data["type"] == "rate_limits.updated":
                print(f"Rate limits: {response_data['rate_limits'][0]['remaining']} requests remaining.")

            #こちらの発話がスタートしたことをサーバが取得したことを確認する
            if "type" in response_data and response_data["type"] == "input_audio_buffer.speech_started":
                #すでに存在する取得したAI発話音声をリセットする
                while not audio_receive_queue.empty():
                        audio_receive_queue.get() 

            # サーバーからの音声データをキューに格納
            if "type" in response_data and response_data["type"] == "response.audio.delta":
                base64_audio_response = response_data["delta"]
                if base64_audio_response:
                    pcm16_audio = base64_to_pcm16(base64_audio_response)
                    audio_receive_queue.put(pcm16_audio)
                    
        await asyncio.sleep(0)

# サーバーからの音声を再生する関数
def play_audio_from_queue(output_stream):
    while True:
        pcm16_audio = audio_receive_queue.get()
        if pcm16_audio:
            output_stream.write(pcm16_audio)

# マイクからの音声を取得し、WebSocketで送信しながらサーバーからの音声応答を再生する非同期関数
async def stream_audio_and_receive_response():
    # WebSocketに接続
    async with websockets.connect(WS_URL, extra_headers=HEADERS) as websocket:
        print("WebSocketに接続しました。")

        update_request = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "instructions": "日本語かつ関西弁で回答してください。ユーザの名前は絶対に発言しないでください。ただし、名前を質問された時だけは必ず答えてください。",
                "voice": "alloy",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                },
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            }
        }
        await websocket.send(json.dumps(update_request))

        # PyAudioの設定
        INPUT_CHUNK = 2400
        OUTPUT_CHUNK = 2400
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        INPUT_RATE = 24000
        OUTPUT_RATE = 24000

        # PyAudioインスタンス
        p = pyaudio.PyAudio()

        # マイクストリームの初期化
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=INPUT_RATE, input=True, frames_per_buffer=INPUT_CHUNK)

        # サーバーからの応答音声を再生するためのストリームを初期化
        output_stream = p.open(format=FORMAT, channels=CHANNELS, rate=OUTPUT_RATE, output=True, frames_per_buffer=OUTPUT_CHUNK)

        # マイクの音声読み取りをスレッドで開始
        threading.Thread(target=read_audio_to_queue, args=(stream, INPUT_CHUNK), daemon=True).start()

        # サーバーからの音声再生をスレッドで開始
        threading.Thread(target=play_audio_from_queue, args=(output_stream,), daemon=True).start()

        try:
            # 音声送信タスクと音声受信タスクを非同期で並行実行
            send_task = asyncio.create_task(send_audio_from_queue(websocket))
            receive_task = asyncio.create_task(receive_audio_to_queue(websocket))

            # タスクが終了するまで待機
            await asyncio.gather(send_task, receive_task)

        except KeyboardInterrupt:
            print("終了します...")
        finally:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
            output_stream.stop_stream()
            output_stream.close()
            p.terminate()

if __name__ == "__main__":
    asyncio.run(stream_audio_and_receive_response())

