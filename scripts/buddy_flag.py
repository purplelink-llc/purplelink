#!/usr/bin/env python3
"""Turn Buddy, the site chat, on or off at once, with no deploy (docs/designs/buddy-chat.md, section 1).

  python3 scripts/buddy_flag.py off      # chat and free checks answer "Buddy is taking a nap and will be back tomorrow"
  python3 scripts/buddy_flag.py on
  python3 scripts/buddy_flag.py status   # flag plus today's and this month's chat spend

Needs the Modal CLI login (uvx --from modal ...). Writes the "flag:enabled" key in the buddy-chat Dict.
"""
import sys
import time

import modal


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    d = modal.Dict.from_name("buddy-chat", create_if_missing=True)
    if cmd in ("on", "off"):
        d["flag:enabled"] = cmd == "on"
    elif cmd != "status":
        print(__doc__)
        return 2
    t = time.gmtime()
    day = d.get(f"spend:day:{time.strftime('%Y-%m-%d', t)}", 0.0)
    month = d.get(f"spend:month:{time.strftime('%Y-%m', t)}", 0.0)
    print(f"enabled={d.get('flag:enabled', True) is not False}  spend today=${day:.4f}  this month=${month:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
