#!/usr/bin/env bash
# Run the FinSL fine-tune on a Verda GPU machine over SSH.
#   ./verda.sh setup   root@IP     copy code + dataset, install Python packages
#   ./verda.sh smoke   root@IP     5 training steps on 64 rows
#   ./verda.sh train   root@IP     full run (in tmux, survives a dropped connection; log: ~/train.log)
#   ./verda.sh predict root@IP     fine-tuned + untrained predictions, copied back to ../../finsl-data/predictions
#   ./verda.sh fetch   root@IP     copy the trained adapter back to ../../finsl-data/models
#   FINSL_MODEL=google/gemma-4-E4B-it OUT=finsl-gemma4-e4b ./verda.sh train root@IP   # the bigger model
#   ./verda.sh serve   root@IP     start the live sign API on port 8000 (key: SIGN_API_KEY in sign_talk/.env)
#   ./verda.sh wipe    root@IP     delete the corpus data from the machine (licence +PRIV) before deleting the instance
set -euo pipefail
cmd=$1; host=$2
here=$(cd "$(dirname "$0")" && pwd); data="$here/../../finsl-data"
run() { ssh -o StrictHostKeyChecking=accept-new "$host" "cd ~/training && $*"; }
model=${FINSL_MODEL:-google/gemma-4-E2B-it}; out=${OUT:-finsl-gemma4-e2b}
py="FINSL_MODEL=$model FINSL_EPOCHS=${FINSL_EPOCHS:-3} .venv/bin/python gpu_train.py"
case $cmd in
  setup)
    rsync -az --exclude .venv --exclude __pycache__ --exclude .pytest_cache "$here/" "$host:training/"
    rsync -az "$data/dataset" "$host:finsl-data/"
    run 'command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH=$HOME/.local/bin:$PATH;
         uv venv -q --python 3.12 --allow-existing && uv pip install -q -r requirements-verda.txt && nvidia-smi --query-gpu=name,memory.total --format=csv' ;;
  smoke)   run "$py train --data ~/finsl-data --out ~/smoke-adapter --limit 64 --max-steps 5" ;;
  train)   run "tmux new -d -s $out '$py train --data ~/finsl-data --out ~/$out 2>&1 | tee ~/train-$out.log'"; echo "started; follow with: ssh $host tail -f train-$out.log" ;;
  predict)
    run "$py predict --data ~/finsl-data --adapter ~/$out --out ~/$out-pred.jsonl && $py predict --data ~/finsl-data --out ~/$out-base-pred.jsonl"
    mkdir -p "$data/predictions"; scp "$host:$out-pred.jsonl" "$host:$out-base-pred.jsonl" "$data/predictions/" ;;
  fetch)   mkdir -p "$data/models"; rsync -az "$host:$out" "$data/models/" ;;
  serve)
    rsync -az "$here/serve.py" "$here/gpu_train.py" "$here/sentence_video.py" "$here/finsl" "$host:training/"
    rsync -az "$data/signbank.json" "$host:finsl-data/"
    grep '^SIGN_API_KEY=' "$here/../.env" | ssh "$host" 'umask 077; cat > ~/sign-api.env'
    run 'export PATH=$HOME/.local/bin:$PATH; uv pip install -q fastapi uvicorn && (tmux kill-session -t api 2>/dev/null || true) &&
         tmux new -d -s api "set -a; . ~/sign-api.env; set +a; FINSL_ADAPTER=~/'"$out"' FINSL_BANK=~/finsl-data/signbank.json FINSL_MODEL='"$model"' .venv/bin/uvicorn serve:app --host 0.0.0.0 --port 8000 2>&1 | tee ~/api.log"'
    echo "starting; log: ssh $host tail -f api.log" ;;
  wipe)    ssh "$host" 'tmux kill-session -t api 2>/dev/null; rm -rf ~/finsl-data ~/*-pred.jsonl ~/sign-api.env' ;;
  *) echo "unknown command $cmd"; exit 1 ;;
esac
