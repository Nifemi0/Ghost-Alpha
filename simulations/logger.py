
import json
import asyncio
import time

class MultiverseLogger:
    def __init__(self, log_path="multiverse_sims.jsonl"):
        self.log_path = log_path

    async def log(self, data):
        try:
            line = json.dumps(data) + "\n"
            await asyncio.get_event_loop().run_in_executor(None, self._write_sync, line)
        except: pass

    def _write_sync(self, line):
        with open(self.log_path, "a") as f:
            f.write(line)
