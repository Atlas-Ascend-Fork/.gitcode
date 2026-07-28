import os
import sys
import json

def write_task_json(warn_num, tool_name):
    data = {
        tool_name: warn_num
    }
    static_file = f"StaticCheck_{tool_name}.json"
    with open(static_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with open(static_file, "r", encoding="utf-8") as f:
        result=json.load(f)

if __name__ == "__main__":
    warn_num = sys.argv[1]
    tool_name = sys.argv[2]
    write_task_json(warn_num, tool_name)