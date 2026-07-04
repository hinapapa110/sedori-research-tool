#!/bin/zsh
# 仕入れ候補発掘ツール GUIランチャー（Finderでダブルクリックして起動）
#
# 注意: macOS標準Pythonのtkinter（Tk 8.5）は既知のバグでCPU100%のままウィンドウが
# 表示されないことがあるため、GUI表示には Homebrew の Tk 8.6 を使う専用の仮想環境
# （.venv-gui）を使う。検索処理（main.py）自体は通常の .venv で実行する。
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "初回セットアップ中です（検索処理用の仮想環境を作成しています）..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi

if [ ! -x ".venv-gui/bin/python" ]; then
  echo "初回セットアップ中です（GUI表示用の環境を作成しています）..."
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrewが見つかりません。https://brew.sh からインストールしてください。"
    echo "（Homebrewなしでも 'python main.py search ...' でCLI検索は利用できます）"
    read -r "?Enterキーで終了します..."
    exit 1
  fi
  brew list python-tk@3.11 >/dev/null 2>&1 || brew install python-tk@3.11
  PY311=$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11
  if [ ! -x "$PY311" ]; then
    PY311=$(brew --prefix)/bin/python3.11
  fi
  "$PY311" -m venv .venv-gui && .venv-gui/bin/pip install -q -r requirements.txt
fi

exec .venv-gui/bin/python gui.py
