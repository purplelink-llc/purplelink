#!/usr/bin/env bash
cd "$(dirname "$0")"
while ! grep -q BATCHDONE /tmp/b4.log; do sleep 10; done
export WDOG=420 RES=1080x1920
echo "== v_ob"; ./cap-v5.sh v_ob v --hud4 --ui=1.4 --botpad=440 --zoom=0.8 --scene=a --seed=9 --blast 2>&1 | tail -1 | cut -c1-60
echo BATCH2DONE
