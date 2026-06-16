import re
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# CONFIGURAZIONE: i nomi devono corrispondere ESATTAMENTE (case-sensitive)
# ai nomi dei ruoli presenti sul server Discord.
# ---------------------------------------------------------------------------
ISTRUTTORE_ROLE_NAME = "Istruttore"

LESSON_ROLES = {
    1: "Lezione 1",
    2: "Lezione 2",
    3: "Lezione 3",
}

# Regex per estrarre gli ID utente da menzioni del tipo <@123456789> o <@!123456789>
MENTION_RE = re.compile(r"<@!?(\d+)>")


class Lezioni(commands.Cog):
    def __init__(self, bot: commands.Bot, log_channel_id: int | None):
        self.bot = bot
        self.log_channel_id = log_channel_id

    # -----------------------------------------------------------------
    # /lezione
    # -----------------------------------------------------------------
    @app_commands.command(
        name="lezione",
        description="Assegna il ruolo di una lezione dell'accademia agli utenti menzionati.",
    )
    @app_commands.describe(
        numero_lezione="Numero della lezione completata (1, 2 o 3)",
        utenti="Menziona uno o più utenti, es: @utente1 @utente2",
    )
    @app_commands.choices(
        numero_lezione=[
            app_commands.Choice(name="Lezione 1", value=1),
            app_commands.Choice(name="Lezione 2", value=2),
            app_commands.Choice(name="Lezione 3", value=3),
        ]
    )
    @app_commands.checks.has_role(ISTRUTTORE_ROLE_NAME)
    @app_commands.guild_only()
    async def lezione(
        self,
        interaction: discord.Interaction,
        numero_lezione: app_commands.Choice[int],
        utenti: str,
    ):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        autore = interaction.user
        numero = numero_lezione.value
        ruolo_nome = LESSON_ROLES[numero]

        ruolo_da_assegnare = discord.utils.get(guild.roles, name=ruolo_nome)
        if ruolo_da_assegnare is None:
            await interaction.followup.send(
                f"⚠️ Errore di configurazione: il ruolo **{ruolo_nome}** non esiste su questo server. "
                "Chiedi a un amministratore di crearlo.",
                ephemeral=True,
            )
            return

        # Estrazione e deduplica degli ID utente menzionati, mantenendo l'ordine
        user_ids = list(dict.fromkeys(int(uid) for uid in MENTION_RE.findall(utenti)))

        if not user_ids:
            await interaction.followup.send(
                "⚠️ Devi menzionare almeno un utente valido. "
                "Esempio: `/lezione numero_lezione:1 utenti:@utente1 @utente2`",
                ephemeral=True,
            )
            return

        promossi: list[str] = []
        gia_presenti: list[str] = []
        errori: list[str] = []

        for uid in user_ids:
            membro = guild.get_member(uid)
            if membro is None:
                try:
                    membro = await guild.fetch_member(uid)
                except discord.NotFound:
                    errori.append(f"<@{uid}> — non trovato su questo server")
                    continue

            # --- Controlli di sicurezza: prerequisiti delle lezioni precedenti ---
            if numero == 2 and not self._has_role(membro, LESSON_ROLES[1]):
                errori.append(f"{membro.mention} — non ha ancora il ruolo **{LESSON_ROLES[1]}**")
                continue

            if numero == 3 and not self._has_role(membro, LESSON_ROLES[2]):
                errori.append(f"{membro.mention} — non ha ancora il ruolo **{LESSON_ROLES[2]}**")
                continue

            # Se l'utente ha già il ruolo, non serve fare nulla (ma lo segnaliamo)
            if self._has_role(membro, ruolo_nome):
                gia_presenti.append(membro.mention)
                continue

            # --- Assegnazione del ruolo (ad accumulo: i ruoli precedenti restano) ---
            try:
                await membro.add_roles(
                    ruolo_da_assegnare,
                    reason=f"{ruolo_nome} completata — assegnata da {autore} ({autore.id})",
                )
                promossi.append(membro.mention)
            except discord.Forbidden:
                errori.append(
                    f"{membro.mention} — il bot non ha i permessi per assegnare il ruolo "
                    "(controlla la gerarchia dei ruoli)"
                )

        embed = self._build_embed(numero, ruolo_nome, autore, promossi, gia_presenti, errori)
        await interaction.followup.send(embed=embed)

        # Invio della copia nel canale di log, se configurato
        if self.log_channel_id:
            canale_log = self.bot.get_channel(self.log_channel_id)
            if canale_log:
                await canale_log.send(embed=embed)

    # -----------------------------------------------------------------
    # Helper
    # -----------------------------------------------------------------
    @staticmethod
    def _has_role(membro: discord.Member, role_name: str) -> bool:
        return any(r.name == role_name for r in membro.roles)

    @staticmethod
    def _build_embed(
        numero: int,
        ruolo_nome: str,
        autore: discord.Member,
        promossi: list[str],
        gia_presenti: list[str],
        errori: list[str],
    ) -> discord.Embed:
        successo = bool(promossi or gia_presenti)

        embed = discord.Embed(
            title=f"{'✅' if successo else '❌'} {ruolo_nome} — Riepilogo",
            color=discord.Color.green() if successo else discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Istruttore", value=autore.mention, inline=False)

        if promossi:
            embed.add_field(name="🎓 Promossi", value="\n".join(promossi), inline=False)
        if gia_presenti:
            embed.add_field(name="ℹ️ Già in possesso del ruolo", value="\n".join(gia_presenti), inline=False)
        if errori:
            embed.add_field(name="⚠️ Non assegnati", value="\n".join(errori), inline=False)

        embed.set_footer(text=f"Accademia LSPD • Lezione {numero}")
        return embed

    # -----------------------------------------------------------------
    # Gestione errori del comando (es. permessi mancanti)
    # -----------------------------------------------------------------
    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingRole):
            messaggio = (
                f"🚫 Non hai il permesso di usare questo comando. "
                f"È riservato al ruolo **{ISTRUTTORE_ROLE_NAME}**."
            )
        elif isinstance(error, app_commands.NoPrivateMessage):
            messaggio = "🚫 Questo comando può essere usato solo all'interno di un server."
        else:
            messaggio = f"⚠️ Si è verificato un errore imprevisto: {error}"

        if interaction.response.is_done():
            await interaction.followup.send(messaggio, ephemeral=True)
        else:
            await interaction.response.send_message(messaggio, ephemeral=True)


async def setup(bot: commands.Bot):
    # Necessario se in futuro si vuole caricare il cog con bot.load_extension("cogs.lezioni")
    await bot.add_cog(Lezioni(bot, None))
