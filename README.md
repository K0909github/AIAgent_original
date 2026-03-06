# Python GUI Agent (Observe → Think → Act)

最小構成のGUIエージェントを置いたサンプルです。

## アーキテクチャ（面接用にそのまま言える版）

GUIエージェントは基本的に **Observe → Think → Act** のループです。

- **Observe（観測）**: スクリーンショット取得（状態の取り込み）
- **Think（計画）**: Vision LLM に画面とタスクを渡し、次の1手を tool calling で決める
- **Act（実行）**: `click/type_text/scroll` 等のツールを実行して画面状態を変える

このリポジトリはそれを次の4レイヤで分けています。

- `perception`: スクショ取得・画像のデータURL化
- `planner`: LLM呼び出し（tool callingで次のアクションを1つ返す）
- `tools/executor`: GUI操作（pyautogui）
- `agent`: ループ制御（最大ステップ、終了条件など）

## 動かし方（ホストでGUIを操作）

### 1) セットアップ

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`.env.example` を `.env` にコピーして `GEMINI_API_KEY` を設定してください。

### 2) 実行（安全のため dry-run 推奨）

```bash
# dry-run: 実際のクリック/入力はしない（スクショ + LLM計画だけ）
python -m gui_agent run --task "ブラウザでGoogleを開いて '松尾研' を検索して" --max-steps 5 --dry-run
```

実操作する場合は `--dry-run` を外してください（注意: マウス/キーボードを本当に操作します）。

## Docker（Plannerだけをコンテナ化）

**重要**: コンテナは通常ホストOSのGUIを直接操作できません。
そこでこのサンプルでは、Dockerは **Planner（LLM呼び出し）だけ**をAPIとして動かし、
GUI操作（pyautogui）はホスト側プロセスで行う構成にしています。

### 1) Planner API 起動

```bash
docker compose up --build
```

### 2) ホスト側エージェントをHTTP Plannerで実行

```bash
python -m gui_agent run --task "ブラウザでGoogleを開いて '松尾研' を検索して" --max-steps 5 --planner http --planner-url http://localhost:8000 --dry-run
```

## Git Flow（PR練習用）

このリポジトリは `main` を安定ブランチとして使う想定です。

### 典型的な流れ

```bash
# 1) 最新化
git checkout main
git pull

# 2) featureブランチ作成
git checkout -b feature/add-xyz

# 3) 変更してコミット
git add .
git commit -m "Add xyz"

# 4) pushしてPR作成
git push -u origin feature/add-xyz
```

PRの説明には次を入れると面接でも強いです。

- 何を作ったか（Observe/Think/Actのどこを触ったか）
- 安全策（dry-runやステップ上限など）
- Docker分離の理由（GUI操作はホスト、Plannerはサービス化）

## 主要ファイル

- [gui_agent/agent.py](gui_agent/agent.py)
- [gui_agent/perception.py](gui_agent/perception.py)
- [gui_agent/planner_gemini.py](gui_agent/planner_gemini.py)
- [gui_agent/tools.py](gui_agent/tools.py)
- [planner_api/main.py](planner_api/main.py)
- [docker-compose.yml](docker-compose.yml)

## 注意

- このコードはデモ用途です。実運用では、クリックの前に検証（UI要素検出、制約、監査ログ等）を入れるのが一般的です。
- 画面に個人情報が映る可能性があるので、スクショ保存やログ取りの扱いに注意してください。
