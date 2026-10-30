#!/bin/zsh
# 仕入れ候補発掘ツール GUIランチャー（Finderでダブルクリックして起動）
#
# 注意: macOS標準Pythonは使わない。
# - tkinter（Tk 8.5）に既知のバグがあり、CPU100%のままウィンドウが表示されないことがある
# - SSLライブラリがLibreSSLのため、脆弱性修正済みの urllib3 2系が動かない
# そのため GUI表示（.venv-gui）も検索処理（.venv）も Homebrew の Python 3.11 で作る。
cd "$(dirname "$0")"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrewが見つかりません。https://brew.sh からインストールしてください。"
  read -r "?Enterキーで終了します..."
  exit 1
fi
brew list python-tk@3.11 >/dev/null 2>&1 || brew install python-tk@3.11
PY311=$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11
if [ ! -x "$PY311" ]; then
  PY311=$(brew --prefix)/bin/python3.11
fi

# 以前の macOS標準Python で作った環境（LibreSSL）が残っていたら作り直す
for v in .venv .venv-gui; do
  if [ -x "$v/bin/python" ] && "$v/bin/python" -c "import ssl; print(ssl.OPENSSL_VERSION)" | grep -q LibreSSL; then
    echo "古い環境（$v）を作り直します..."
    rm -rf "$v"
  fi
done

if [ ! -x ".venv/bin/python" ]; then
  echo "初回セットアップ中です（検索処理用の仮想環境を作成しています）..."
  "$PY311" -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi

if [ ! -x ".venv-gui/bin/python" ]; then
  echo "初回セットアップ中です（GUI表示用の環境を作成しています）..."
  "$PY311" -m venv .venv-gui && .venv-gui/bin/pip install -q -r requirements.txt
fi

# requirements.txt が更新されていたら反映（urllib3 など）
for v in .venv .venv-gui; do
  if [ requirements.txt -nt "$v/.installed" ]; then
    "$v/bin/pip" install -q -r requirements.txt && touch "$v/.installed"
  fi
done

exec .venv-gui/bin/python gui.py
