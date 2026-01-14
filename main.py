
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from ui.bot import setup_bot, set_commands
from core.engine import DualEngine
import config.constants as C

# Master Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LatencyGhost")
handler = RotatingFileHandler("trade_log.txt", maxBytes=5*1024*1024, backupCount=5)
logger.addHandler(handler)

async def main():
    print("🔥 DUAL ENGINE V2.6 MODULAR ACTIVE")
    
    # 1. Setup UI
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    application = setup_bot(token)
    
    # 2. Setup Core Engine
    engine = DualEngine(application)
    application.bot_data['engine'] = engine
    
    # 3. Set Menu Commands
    await set_commands(application)
    
    # 4. Start Monitoring Tasks
    asyncio.create_task(engine.binance_monitor.run())
    asyncio.create_task(engine.poly_monitor.run())
    asyncio.create_task(engine.batcher.run_flusher())
    asyncio.create_task(engine.run_market_scout())
    asyncio.create_task(engine.run_master_loop())
    
    # 5. Run Polling
    print("🚀 GHOST IN THE SHELL: System Operational.")
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Keep alive
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 System Shutdown initiated.")
