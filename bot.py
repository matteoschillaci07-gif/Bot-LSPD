import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN=MTUxNjQ3MzMyMTQ1MjIxMjI5Ng.GWYJ4A.if_Qb6zNZJmcGMbpGlARfkIIWa1ogE-ASXOJ4k
GUILD_ID=1516220949287145603
LOG_CHANNEL_ID=

# Intents necessari: dobbiamo poter leggere i membri e i loro ruoli
intents = discord.Intents.default()
intents.members = True  # Richiede di abilitare "Server Members Intent" nel Developer Portal


class AccademiaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Carichiamo il cog che contiene il comando /lezione
        from cogs.lezioni import Lezioni

        log_channel_id = int(LOG_CHANNEL_ID) if LOG_CHANNEL_ID else None
        await self.add_cog(Lezioni(self, log_channel_id))

        # Sincronizzazione dei comandi slash
        if GUILD_ID:
            # Sync solo su un server specifico: i comandi compaiono quasi istantaneamente (utile in fase di test)
            guild_obj = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
        else:
            # Sync globale: può richiedere fino a un'ora per propagarsi su tutti i server
            await self.tree.sync()


bot = AccademiaBot()


@bot.event
async def on_ready():
    print(f"✅ Bot connesso come {bot.user} (ID: {bot.user.id})")
    print("Pronto a gestire le lezioni dell'accademia LSPD.")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "❌ Token non trovato. Crea un file .env con DISCORD_TOKEN=il_tuo_token (vedi .env.example)."
        )
    bot.run(TOKEN)
