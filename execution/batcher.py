
import asyncio

class MessageBatcher:
    def __init__(self, bot):
        self.bot = bot
        self.queue = {} # {user_id: [results]}

    def add_to_batch(self, user_id, result):
        if user_id not in self.queue:
            self.queue[user_id] = []
        self.queue[user_id].append(result)

    async def run_flusher(self):
        """Monitors settlement queue and flushes unified reports to users."""
        while True:
            await asyncio.sleep(1.5)
            uids = list(self.queue.keys())
            for uid in uids:
                batch = self.queue.pop(uid, [])
                if not batch: continue
                
                total_p = sum(r['profit'] for r in batch)
                rows = ""
                for r in batch:
                    rows += f"• `{r['id']}`: {r['emoji']} `${r['profit']:+.2f}` | `{r['reason']}`\n"
                
                final_bal = batch[-1]['final_bal']
                
                summary = (
                    f"📝 *BATCH SETTLEMENT REPORT*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 **Trades Settled:** `{len(batch)}`\n"
                    f"{rows}"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 **Total Result:** `${total_p:+.4f}` 🔥\n"
                    f"💰 **Wallet Balance:** `${final_bal:.2f}`"
                )
                try:
                    await self.bot.send_message(chat_id=uid, text=summary, parse_mode='Markdown')
                except Exception as e:
                    print(f"❌ [BATCHER] Broadcast error to {uid}: {e}")
