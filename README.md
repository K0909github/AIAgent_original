# Dockerだけで動く Web AI Agent（Observe → Think → Act）

このリポジトリは「Dockerだけで完結する」最小のAIエージェント例です。
**コンテナ内ブラウザ（Playwright）を操作**し、画面（スクショ）をGeminiに渡して次の行動を決めます。

## アーキテクチャ

エージェントは基本的に **Observe → Think → Act** のループです。

- **Observe（観測）**: ブラウザのスクリーンショット取得
- **Think（計画）**: Gemini（Vision + function calling）で「次の1手」を1回だけ決める
- **Act（実行）**: Playwrightで `goto/click/type/press/wait` を実行

このリポジトリは、最小限の3つに分けています。

- `web_agent`: ブラウザ操作（Observe/Act）
- `planner_api`: Geminiに「次の1手」を問い合わせるAPI（Think）
- `docker-compose.yml`: 2つのコンテナをつなぐ実行定義

## 使い方（Dockerだけ）

### 1) APIキーを設定

[.env.example](.env.example) を `.env` にコピーして `GEMINI_API_KEY` を入れます。

任意で `.env` にタスクを入れると、コマンドが短くなります。

```env
WEB_AGENT_TASK=DuckDuckGoで '松尾研' を検索して
WEB_AGENT_MAX_STEPS=8
WEB_AGENT_START_URL=https://duckduckgo.com
```

### 2) 実行（これだけ）

```bash
docker compose up --build --abort-on-container-exit --exit-code-from web-agent
```

実行後、スクリーンショットはホスト側の `screens/` に保存されます。

注意: Google は自動操作（Playwright/headless 等）に対して CAPTCHA（"unusual traffic" / "verify you are not a robot"）を出すことがあり、その場合はエージェントが操作を継続できません。
そのときは `WEB_AGENT_START_URL` を DuckDuckGo などに変えるのが簡単です。

補足: VS Code の Dev Containers などで **Dockerデーモンがワークスペースとは別のホスト** で動いている場合、`./screens` の bind mount がこのワークスペースに反映されず「保存されていない」ように見えることがあります。
その場合は、コンテナから `docker cp` で回収するラッパーを使ってください。

```bash
./scripts/run_docker.sh
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

PRの説明には次を入れる

- 何を作ったか（Observe/Think/Actのどこを触ったか）
- 安全策（dry-runやステップ上限など）
- Docker構成の理由（ブラウザ操作はweb-agent、LLM呼び出しはplanner_apiに分離）

## VS Codeで開く（Dev Containers）

VS CodeのDev Containers拡張を使う場合は、コマンドパレットから
`Dev Containers: Reopen in Container` を実行します（設定は [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)）。

## 主要ファイル
- [Explain.md](Explain.md)（コード完全解説）
- [planner_api/main.py](planner_api/main.py)
- [docker-compose.yml](docker-compose.yml)
- [web_agent/agent.py](web_agent/agent.py)
- [web_agent/tools.py](web_agent/tools.py)
- [web_agent/planner_http.py](web_agent/planner_http.py)

## 注意

- このコードはデモ用途です。実運用では、クリックの前に検証（UI要素検出、制約、監査ログ等）を入れるのが一般的です。
- 画面に個人情報が映る可能性があるので、スクショ保存やログ取りの扱いに注意してください。
