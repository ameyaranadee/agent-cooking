from __future__ import annotations
import asyncio
import logging
import os
from pathlib import Path
from tracemalloc import Snapshot
from typing import Any
from daytona import AsyncDaytona, CreateSandboxFromSnapshotParams
from agents import Agent, AsyncComputer, Button, ComputerTool, Environment, Runner, trace
from call_daytona import DaytonaAsyncComputer

from dotenv import load_dotenv
load_dotenv()

assert os.environ.get("DAYTONA_API_KEY"), "DAYTONA_API_KEY is not set."
assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY is not set."
logger = logging.getLogger("computer_use_with_daytona")

# Desktop snapshot that ships with a browser and a desktop environment.
_DESKTOP_SNAPSHOT = "daytonaio/sandbox:0.6.0"
# Where the form lives inside the sandbox, and the port we serve it on.
_FORM_DIR = "/home/daytona/form"
_SERVER_PORT = 8080
# The applicant facts the agent must enter.
APPLICANT_DATA = Path("fake_applicant_data.txt").read_text()
INSTRUCTIONS = """\
You control a remote Linux desktop via mouse, keyboard, and screenshots.
A conference registration form is being served at http://localhost:8080.
When asked to fill the form:
1. Open a browser (look for one in the taskbar or application menu).
2. Navigate to http://localhost:8080.
3. Fill every field using the applicant data the user provides. The form
   spans multiple sections, so scroll down to see them all.
4. Click "Complete Registration".
5. When you see the "Registration Complete!" confirmation, take a screenshot
   and say DONE.
"""
TASK = f"Fill the conference registration form with this applicant data:\n\n{APPLICANT_DATA}"

async def serve_form(sandbox: Any) -> None:
    form_html = Path("form.html").read_bytes()
    await sandbox.fs.create_folder(_FORM_DIR, "0755")
    await sandbox.fs.upload_file(form_html, f"{_FORM_DIR}/index.html")
    print(f"Form uploaded to {_FORM_DIR}/index.html")

    # Redirect output so exec() returns instead of waiting on the server's pipes.
    await sandbox.process.exec(
        f"sh -c 'cd {_FORM_DIR} && python3 -m http.server {_SERVER_PORT} "
        f"> /tmp/httpd.log 2>&1 &'"
    )
    for _ in range(10):
        check = await sandbox.process.exec(
            f"curl -sf -o /dev/null http://localhost:{_SERVER_PORT}/"
        )
        if check.exit_code == 0:
            break
        await asyncio.sleep(0.5)
    else:
        raise RuntimeError(f"HTTP server did not respond on port {_SERVER_PORT}")
    print(f"HTTP server started on port {_SERVER_PORT}")

async def run_agent(sandbox: Any) -> None:
    async with DaytonaAsyncComputer(sandbox) as computer:
        recording = await sandbox.computer_use.recording.start("form-fill")
        print(f"Recording started: {recording.id}")
        try:
            with trace("Daytona form-fill"):
                agent = Agent(
                    name="Form filler",
                    instructions = INSTRUCTIONS,
                    tools = [ComputerTool(computer=computer)],
                    model="gpt-5.4"
                )
                result = await Runner.run(agent, TASK, max_turns=50)
                print(f"\n--- FINAL OUTPUT ---\n{result.final_output}")
        finally:
            stopped = await sandbox.computer_use.recording.stop(recording.id)
            print(f"\nRecording stopped: {stopped.file_name} ({stopped.status})")
            local_recording_path = Path(stopped.file_name).name
            await sandbox.computer_use.recording.download(recording.id, local_recording_path)
            print(f"Recording downloaded to: {local_recording_path}")

async def main() -> None:
    print("Starting computer use agent")
    daytona = AsyncDaytona()
    sandbox = await daytona.create(
        CreateSandboxFromSnapshotParams(snapshot = _DESKTOP_SNAPSHOT)
    )
    print(f"Sandbox ready: {sandbox.id}")

    try:
        await serve_form(sandbox)
        await run_agent(sandbox)
    finally:
        await daytona.delete(sandbox)
        print(f"Sandbox {sandbox.id} deleted.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("log.txt", mode="w"),
            logging.StreamHandler(),
        ],
    )
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("Run failed")
        raise