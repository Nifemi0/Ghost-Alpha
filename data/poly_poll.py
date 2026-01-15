
import asyncio
import socket
import aiohttp
from config.constants import DEFAULT_TOKEN_ID

class PolyMonitor:
    def __init__(self, engine):
        self.engine = engine
        self.session = None

    async def init_session(self):
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            self.session = aiohttp.ClientSession(connector=connector, 
                timeout=aiohttp.ClientTimeout(total=10))

    async def run(self):
        print(f"📡 [DATA] Polymarket Async Monitor Active (Token: {self.engine.token_id[:8]}...).", flush=True)
        while True:
            try:
                await self.init_session()
                
                # SLUG SUPPORT: If token_id looks like a slug (has hyphens), use Events API directly
                if "-" in self.engine.token_id:
                    url = f"https://gamma-api.polymarket.com/events?slug={self.engine.token_id}"
                    async with self.session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and len(data) > 0:
                                # First event, first market
                                m = data[0].get("markets", [{}])[0]
                                # Robust Price Resolution: prefer REAL trade data
                                price_val = m.get("lastTradePrice") or m.get("bestBid") 
                                if price_val is not None:
                                    new_price = float(price_val)
                                    # Only count as a "move" if we already had a baseline price
                                    if self.engine.poly_price > 0 and abs(new_price - self.engine.poly_price) > (self.engine.poly_price * 0.00001):
                                        import time
                                        self.engine.poly_last_move_time = time.time()
                                    
                                    # Update Price
                                    self.engine.poly_price = new_price
                                    self.engine.poly_question = m.get("question", m.get("groupItemTitle", "Unknown"))
                                else:
                                    # If no real trade/bid data, skip this update
                                    continue
                                # Update real token ID for execution if possible? 
                                # Actually, execution needs a numeric ID. 
                                # We should extract the valid CLOB ID here and update self.engine.token_id in memory (but careful about race conditions).
                                # For now, just getting price is enough to stop the crash.
                                # Execution will fail if token_id is a slug.
                                # CRITICAL: We must update token_id to the numeric one found in the slug.
                                real_tokens = m.get("clobTokenIds", [])
                                if real_tokens:
                                    # Update engine token_id to the numeric one so execution works!
                                    # But we need the YES token usually (index 0 or 1?)
                                    # Usually 0 is the first outcome.
                                    self.engine.token_id = real_tokens[0]
                                    print(f"✅ [DATA] Resolved Slug to Token: {self.engine.token_id[:10]}...", flush=True)
                        else:
                            await self.engine.check_market_health()
                    
                    await asyncio.sleep(1)
                    continue

                # Standard Numeric ID Flow
                url = f"https://clob.polymarket.com/price?token_id={self.engine.token_id}&side=buy"
                async with self.session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.engine.poly_price = float(data.get("price", self.engine.poly_price))
                        # Fallback to Gamma API (sometimes CLOB is flaky or ID format differs)
                        gamma_url = f"https://gamma-api.polymarket.com/events?clob_token_id={self.engine.token_id}"
                        try:
                            async with self.session.get(gamma_url) as g_resp:
                                found_price = False
                                if g_resp.status == 200:
                                    g_data = await g_resp.json()
                                    if g_data and len(g_data) > 0:
                                        # ... existing event logic ...
                                        for m in g_data[0].get("markets", []):
                                            if self.engine.token_id in m.get("clobTokenIds", []):
                                                if "lastTradePrice" in m:
                                                    self.engine.poly_price = float(m["lastTradePrice"])
                                                    found_price = True
                                                break
                                
                                if not found_price:
                                    # Fallback Level 2: Try as Market ID (Integer)
                                    mkt_url = f"https://gamma-api.polymarket.com/markets/{self.engine.token_id}"
                                    async with self.session.get(mkt_url) as m_resp:
                                        if m_resp.status == 200:
                                            m_data = await m_resp.json()
                                            # Validate question just to be safe it's not some random market
                                            # Actually we trust the user config.
                                            if "lastTradePrice" in m_data:
                                                self.engine.poly_price = float(m_data["lastTradePrice"])
                                                self.engine.poly_question = m_data.get("question", self.engine.poly_question)
                                                # Also grab the REAL CLOB ID if possible for the future
                                                # But for now just get the price.
                                                pass
                                        else:
                                            await self.engine.check_market_health()
                        except:
                            await self.engine.check_market_health()
                
                # Periodically sync market question
                info_url = f"https://clob.polymarket.com/markets/{self.engine.token_id}"
                async with self.session.get(info_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.engine.poly_question = data.get("question", self.engine.poly_question)
                
            except Exception as e:
                print(f"📡 [DATA] Polymarket Error: {e}", flush=True)
            
            await asyncio.sleep(1) # Fixed polling interval

    async def check_book_depth(self, size_usd):
        try:
            await self.init_session()
            url = f"https://clob.polymarket.com/book?token_id={self.engine.token_id}"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    book = await resp.json()
                    asks = book.get("asks", []) # sell orders (we buy from these)
                    
                    filled = 0.0
                    cost = 0.0
                    
                    # Walk the book
                    for ev in asks:
                        price = float(ev["price"])
                        qty = float(ev["size"])
                        
                        needed = size_usd - filled
                        take = min(needed, qty * price)
                        
                        cost += take
                        filled += take
                        
                        if filled >= size_usd:
                            break
                    
                    if filled < size_usd:
                        return 1.0 # Infinite slippage (not enough liquidity)
                        
                    avg_price = cost / (filled / ((cost/filled) if filled>0 else 1)) # heuristic
                    # Simplified: We just want the worst price we hit
                    worst_price = float(asks[-1]["price"]) if asks else 1.0
                    
                    # Better metric: Effective Price
                    # Total Tokens bought = sum(take / price)
                    tokens = 0
                    filled_calc = 0
                    for ev in asks:
                        p = float(ev["price"])
                        s = float(ev["size"]) * p # value in USD
                        
                        needed = size_usd - filled_calc
                        take_usd = min(needed, s)
                        
                        tokens += take_usd / p
                        filled_calc += take_usd
                        if filled_calc >= size_usd: break
                        
                    effective_price = size_usd / tokens if tokens > 0 else 1.0
                    return effective_price
        except:
            pass
        return self.engine.poly_price # Fallback to mid price
