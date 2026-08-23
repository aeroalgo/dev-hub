from __future__ import annotations

import argparse
import sys
import time


parser = argparse.ArgumentParser()
parser.add_argument(
    "behavior",
    choices=["clean", "hang", "noise", "tool-then-noise"],
)
args = parser.parse_args()

if args.behavior == "clean":
    print("stdout: clean", flush=True)
    print("stderr: clean", file=sys.stderr, flush=True)
elif args.behavior == "noise":
    while True:
        print(
            '{"type":"stream_event","event":{"type":"content_block_delta",'
            '"delta":{"type":"input_json_delta","partial_json":"x"}}}',
            flush=True,
        )
        time.sleep(0.05)
elif args.behavior == "tool-then-noise":
    print(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"t1"}]}}',
        flush=True,
    )
    while True:
        print(
            '{"type":"stream_event","event":{"type":"content_block_delta",'
            '"delta":{"type":"input_json_delta","partial_json":"y"}}}',
            flush=True,
        )
        time.sleep(0.05)
else:
    print("stdout: hanging", flush=True)
    print("stderr: hanging", file=sys.stderr, flush=True)
    while True:
        time.sleep(1)
