
# コード完全解説（Docker-only Web AI Agent）

このドキュメントは、このリポジトリの **Dockerだけで動く Web AI Agent** を分解して説明します。

やっていることを一言でいうと：

- `web_agent` が **Playwrightでブラウザを操作**してスクショを撮る（Observe/Act）
- `planner_api` が **Gemini（画像 + function calling）で次の1手を決める**（Think）

> 注意: `.env` に入れる `GEMINI_API_KEY` は秘密情報なのでGitにコミットしません（`.gitignore` で無視されています）。

---

## 全体の処理フロー（まず把握）

```
ユーザーが docker compose 実行
		  ↓
web_agent/cli.py               ← 入口。引数を受け取る
		  ↓
web_agent/agent.py             ← メインループ（Observe→Think→Act）
	  ↙        ↘
web_agent/perception.py   web_agent/tools.py   ← Observe担当 / Act担当
		  ↓
web_agent/planner_http.py       ← Think担当（HTTPで外部に投げる）
		  ↓
【ネットワーク越し】
		  ↓
planner_api/main.py             ← planner-apiコンテナ側（Geminiへ問い合わせ）
		  ↓
Gemini API                      ← 実際にAIが「次の1手」を決める
```

Observe→Think→Act の対応は次の通りです。

- **Observe（観測）**: `page.screenshot()` で画面を取る + 送信用に data URL へ変換
- **Think（計画）**: `planner_api` が Gemini に問い合わせ、**「次に呼ぶべきツール」を1回だけ**返す
- **Act（実行）**: `WebToolExecutor.execute()` が Playwright 操作（goto/click/type/press/wait）を実行

---

## 📄 web_agent/cli.py（入口：コマンド引数）

`argparse` はコマンドライン引数を解析するPython標準ライブラリです。

### 受け付けるコマンド

例（コンテナ内での実行イメージ）：

```bash
python -m web_agent run \
  --task "DuckDuckGoで松尾研を検索して" \
  --max-steps 8 \
  --start-url https://duckduckgo.com
```

ポイント：

- `sub.add_subparsers(...)` は「サブコマンド」を作ります。現状は `run` のみ。
- `main()` は **引数を `AgentConfig` に詰めて `WebAgent.run()` を呼ぶだけ**。
- `return 0/1` はプロセスの終了コード。`docker compose ... --exit-code-from web-agent` でこの値が使われます。

> 補足: `--start-url` のデフォルトはコード上は `https://duckduckgo.com` です。
> ただし Compose では `--start-url` を渡しているので、実運用は `.env` / `docker-compose.yml` 側の値が優先されます。

---

## 📄 web_agent/agent.py（メインループ：Observe→Think→Act）

### AgentConfig（設定）

```python
@dataclass
class AgentConfig:
	 task: str
	 max_steps: int = 10
	 planner_url: str = "http://planner:8000"
	 start_url: str = "https://www.google.com"
	 screenshot_dir: str = "screens"
```

`@dataclass` は `__init__` などを自動生成し、設定用クラスを簡潔にします。

### WebAgent の初期化

- `HTTPPlanner(planner_url)` を生成して、以後の Think（計画）をすべてHTTP経由にします
- `_last_tool_result` に「前のステップで何が起きたか」を保持し、次の Think に渡します

これで Gemini が「さっきクリックしたけど変化がない」などの文脈を持てます。

### run() の流れ（重要）

1) スクショ保存ディレクトリ作成

- `os.makedirs(..., exist_ok=True)` でディレクトリがあってもエラーにしない

2) Playwrightでブラウザ起動

```python
with sync_playwright() as p:
	 browser = p.chromium.launch(headless=True)
```

- `headless=True` は画面表示なし。コンテナ内なので基本これが前提です。

3) ページ生成と初期遷移

```python
context = browser.new_context(viewport={"width": 1280, "height": 720})
page = context.new_page()
page.goto(start_url, wait_until="domcontentloaded")
```

- `wait_until="domcontentloaded"` はHTMLの読み込み完了まで待つ（`load` より速い）

4) ループ（最大 `max_steps`）

#### Observe

```python
png = page.screenshot(full_page=True)
shot = WebScreenshot(png_bytes=png, width=vw, height=vh)
```

- `full_page=True` でページ全体を撮れます（デバッグしやすい）

#### Think

```python
action, reason = self._planner.plan(
	 task=task,
	 screenshot=shot,
	 step=step,
	 max_steps=max_steps,
	 last_tool_result=self._last_tool_result,
	 page_url=page.url,
)
```

- `planner_http.py` を通して `planner_api` にPOSTし、Geminiに「次の1手」を問い合わせます
- `page_url` を渡して「いまどこにいるか」の文脈も補強します

#### スクショ保存（デバッグ）

```python
open(..., "wb").write(png)
```

- PNGはバイナリなので `"wb"` が必要です

#### Act

- `action is None`（Geminiがツールを返さなかった/返せなかった）ならスキップして次へ
- `executor.execute(action.name, action.arguments)` でツールを実行
- `done` が返ったらタスク完了として `return`

---

## 📄 web_agent/perception.py（スクショのデータ変換）

JSONで画像（バイナリ）を送れないので、HTTPで送りやすいように **data URL** に変換します。

```python
def to_data_url(self) -> str:
	 b64 = base64.b64encode(self.png_bytes).decode("ascii")
	 return f"data:image/png;base64,{b64}"
```

変換の意味：

```
PNG（bytes）
	↓ base64.b64encode
英数字のテキストに変換
	↓ decode("ascii")
Pythonの str にする
	↓ data URL 化
data:image/png;base64,......
```

---

## 📄 web_agent/planner_http.py（コンテナ間通信：Thinkの橋渡し）

`web_agent` は「AIに考えさせる」部分を直接持たず、HTTPで `planner_api` に投げます。

### PlannedAction

Geminiが返す「次のアクション」を表します。

```python
@dataclass(frozen=True)
class PlannedAction:
	 name: str
	 arguments: Dict[str, Any]
```

例：

- `name="click"`, `arguments={"selector": "input[name=q]"}`

### HTTPPlanner.plan()

ポイントだけ抜粋：

- `base_url.rstrip("/")`：末尾スラッシュ有無の両方に対応
- payload に `image_data_url` と `last_tool_result` を詰める
- `requests.post(..., timeout=120)`：Gemini呼び出しが遅いときに備えて2分
- `raise_for_status()`：4xx/5xx を例外化（異常は早く落として原因特定しやすくする）

レスポンスは `{"action": {"name": ..., "arguments": ...}, "reason": ...}` の形で返ってきます。

---

## 📄 web_agent/tools.py（Act：ブラウザ操作の実体）

ここが「Geminiが返したツール名を、実際のPlaywright操作に変換する」層です。

`execute(name, arguments)` は、ツール名ごとに分岐して処理します。

### goto

- `page.goto(url, wait_until="domcontentloaded")`

### click

- `page.locator(selector).first.click(timeout=10_000)`
- `.first` は複数マッチ時に先頭を使う（安全側）

### type

```python
loc.click(); loc.fill(""); loc.type(text)
```

この3段階が重要です。

- click：フォーカス
- fill("")：既存値のクリア
- type：キー入力イベントを発生させながら入力（サイトによって必要）

### press

- `page.keyboard.press(key)`
- 例：`Enter`, `Tab`

### wait

- `time.sleep(seconds)`
- 画面遷移やアニメ待ち用（雑に見えるがデモ用途として最小）

### done

- タスク完了の合図。`agent.py` 側で `done` を受けると `return` して終了します。

---

## 📄 planner_api/main.py（planner-api：Geminiに考えさせる）

ここは **「AIに次の1手を決めさせる」サーバ** です。

### FastAPI と Pydantic

- `FastAPI`：APIサーバ
- `BaseModel`（Pydantic）：リクエスト/レスポンスの型とバリデーション

`PlanRequest` の重要フィールド：

- `task`：タスク文字列（`web_agent` 側でURL文脈が足される）
- `step/max_steps`：現在のステップ
- `screen_size`：スクショの幅/高さ
- `image_data_url`：スクショ（data URL）
- `last_tool_result`：前の実行結果

### ツール定義（function callingの仕様書）

`_tool_specs()` が Gemini に伝える「使って良いツール一覧」です。

- `goto(url)`
- `click(selector)`
- `type(selector, text)`
- `press(key)`
- `wait(seconds)`
- `done(message?)`

ここがあることで Gemini は **自由文ではなく、ツール呼び出し（function_call）として**次の行動を返せます。

### 画像の逆変換（data URL → bytes）

`image_data_url` は `data:image/png;base64,...` の形なので、`,` で分割して base64 をデコードします。

### ToolConfig（重要）

```python
mode="ANY"
allowed_function_names=[...]
```

- `mode="ANY"`：**必ずツール呼び出しを選ぶ**よう強制（テキストだけ返すのを抑制）
- `allowed_function_names`：このリスト外のツール呼び出しを抑制

### Gemini への入力（テキスト + 画像）

- テキスト：タスク、現在ステップ、画面サイズ、前回結果など
- 画像：スクショPNG

これで Gemini は「いま画面がどう見えているか」を前提に次の1手を決めます。

### 返却（function_call の抽出）

Geminiのレスポンス候補（`candidates`）から `function_call` を探し、見つけたら：

- `action={"name": ..., "arguments": ...}`
- `reason="tool_call:..."`

見つからなければ `action=None` になり、`web_agent/agent.py` 側で「スキップして次のステップへ」になります。

---

## 📄 web_agent/__main__.py / __init__.py（パッケージとして動かすため）

### __main__.py

`python -m web_agent ...` を可能にするエントリーポイントです。

### __init__.py

- `__version__ = "0.1.0"` を定義
- `__all__` で公開名を制限

---

## 全体のデータの流れ（まとめ）

```
① web_agent/cli.py
	引数パース → AgentConfig生成

② web_agent/agent.py（ループ）
	Observe: page.screenshot(full_page=True)
		↓
	perception.py: PNG(bytes) → data URL(str)
		↓
	Think: planner_http.py
		HTTP POST /plan → planner_api
		↓
	planner_api/main.py: Gemini Vision + function calling
		スクショ + テキスト → 次のアクション
		↓
	Act: tools.py
		goto/click/type/press/wait
		↓
	done? → 終了 / else → 次ステップへ
```

