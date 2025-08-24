# main.py
import argparse
import os
import subprocess
import sys

BOT_TO_SCRIPT = {
    "uts_events": "main_uts_events.py",
    "prosple": "main_prosple.py",
}

def main():
    parser = argparse.ArgumentParser(description="Run selected Discord bot.")
    parser.add_argument(
        "--bot",
        default=os.getenv("BOT_NAME", "uts_events"),
        choices=BOT_TO_SCRIPT.keys(),
        help="Which bot to run (uts_events or prosple)",
    )
    args = parser.parse_args()

    script = BOT_TO_SCRIPT[args.bot]
    print(f"[router] Launching: {script}")
    result = subprocess.run([sys.executable, script], check=False)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
