import asyncio
import ccxt.pro as ccxtpro

async def test():
    exchange = ccxtpro.binance()
    try:
        print("Testing Binance Connection...")
        ticker = await exchange.watch_ticker('BTC/USDT')
        print(f"Success! Price: {ticker['last']}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.close()

asyncio.run(test())
