import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import os
import random
from datetime import datetime, timedelta

ARQUIVO = "financas.json"
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=['b', 'B'], intents=intents, case_insensitive=True)

# === Utilidades JSON ===
def carregar_dados():
    if not os.path.exists(ARQUIVO):
        return {"usuarios": {}, "vips": {}}
    with open(ARQUIVO, "r") as f:
        return json.load(f)

def salvar_dados(dados):
    with open(ARQUIVO, "w") as f:
        json.dump(dados, f, indent=2)

def parse_valor(texto):
    texto = texto.lower().replace(",", ".")
    if texto.endswith("kk"):
        return float(texto[:-2]) * 1_000_000
    if texto.endswith("k"):
        return float(texto[:-1]) * 1_000
    if texto.endswith("m"):
        return float(texto[:-1]) * 1_000_000
    return float(texto)

def saldo_usuario(user_id):
    dados = carregar_dados()
    return dados["usuarios"].get(str(user_id), {}).get("saldo", 0)

def alterar_saldo(user_id, valor):
    dados = carregar_dados()
    uid = str(user_id)
    if uid not in dados["usuarios"]:
        dados["usuarios"][uid] = {"saldo": 0, "transacoes": []}
    dados["usuarios"][uid]["saldo"] += valor
    salvar_dados(dados)

def registrar_transacao(user_id, tipo, valor, descricao):
    dados = carregar_dados()
    uid = str(user_id)
    if uid not in dados["usuarios"]:
        dados["usuarios"][uid] = {"saldo": 0, "transacoes": []}
    transacao = {
        "tipo": tipo,
        "valor": valor,
        "descricao": descricao,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    dados["usuarios"][uid]["transacoes"].append(transacao)
    salvar_dados(dados)

def get_autorizados():
    dados = carregar_dados()
    return dados.get("autorizados", [])

def adicionar_autorizado(user_id):
    dados = carregar_dados()
    if "autorizados" not in dados:
        dados["autorizados"] = []
    if user_id not in dados["autorizados"]:
        dados["autorizados"].append(user_id)
        salvar_dados(dados)

def remover_autorizado(user_id):
    dados = carregar_dados()
    if "autorizados" in dados and user_id in dados["autorizados"]:
        dados["autorizados"].remove(user_id)
        salvar_dados(dados)

def eh_autorizado(user_id):
    return user_id in get_autorizados()

# === Comandos ===
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

@bot.command()
async def saldo(ctx):
    saldo = saldo_usuario(ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, seu saldo é R$ {saldo:,.2f}")

@bot.command()
async def duelar(ctx, membro: discord.Member, valor: str):
    try:
        valor_num = parse_valor(valor)
    except:
        return await ctx.send("❌ Valor inválido. Ex: 10k, 1m...")

    if membro.id == ctx.author.id:
        return await ctx.send("🙄 Você não pode duelar com você mesmo!")

    if saldo_usuario(ctx.author.id) < valor_num or saldo_usuario(membro.id) < valor_num:
        return await ctx.send("⚠️ Ambos precisam ter saldo suficiente.")

    class DueloView(View):
        def __init__(self):
            super().__init__(timeout=60)

        @discord.ui.button(label="Aceitar Duelo", style=discord.ButtonStyle.green)
        async def aceitar(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != membro.id:
                return await interaction.response.send_message("❌ Apenas o desafiado pode aceitar.", ephemeral=True)
            self.stop()
            vencedor = random.choice([ctx.author, membro])
            perdedor = membro if vencedor == ctx.author else ctx.author

            alterar_saldo(vencedor.id, valor_num)
            alterar_saldo(perdedor.id, -valor_num)

            registrar_transacao(vencedor.id, "receita", valor_num, f"Ganhou duelo contra {perdedor.name}")
            registrar_transacao(perdedor.id, "despesa", valor_num, f"Perdeu duelo para {vencedor.name}")

            await interaction.message.edit(content=f"⚔️ Duelo entre {ctx.author.mention} e {membro.mention} finalizado! 🏆 {vencedor.mention} ganhou R$ {valor_num:,.2f}!", view=None)

        @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red)
        async def recusar(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != membro.id:
                return await interaction.response.send_message("❌ Apenas o desafiado pode recusar.", ephemeral=True)
            self.stop()
            await interaction.message.edit(content="❌ Duelo recusado.", view=None)

    view = DueloView()
    await ctx.send(f"🎯 {ctx.author.mention} desafiou {membro.mention} para um duelo de R$ {valor_num:,.2f}", view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def setvip(ctx, membro: discord.Member, dias: int):
    dados = carregar_dados()
    expira = datetime.now() + timedelta(days=dias)
    dados["vips"][str(membro.id)] = {
        "expira_em": expira.strftime("%Y-%m-%d %H:%M:%S"),
        "ultimo_claim": None,
        "custom": ""
    }
    salvar_dados(dados)
    await ctx.send(f"💎 {membro.mention} recebeu VIP por {dias} dias!")

@bot.command()
async def vipclaim(ctx):
    dados = carregar_dados()
    uid = str(ctx.author.id)
    vip = dados["vips"].get(uid)
    if not vip:
        return await ctx.send("❌ Você não é VIP.")
    agora = datetime.now()
    expira = datetime.strptime(vip["expira_em"], "%Y-%m-%d %H:%M:%S")
    if agora > expira:
        return await ctx.send("⛔ Seu VIP expirou.")
    if vip["ultimo_claim"]:
        ultimo = datetime.strptime(vip["ultimo_claim"], "%Y-%m-%d %H:%M:%S")
        if (agora - ultimo).total_seconds() < 18000:
            restante = timedelta(seconds=18000) - (agora - ultimo)
            return await ctx.send(f"⏳ Espere {restante} para coletar novamente.")
    alterar_saldo(ctx.author.id, 250)
    registrar_transacao(ctx.author.id, "receita", 250, "Recompensa VIP")
    dados["vips"][uid]["ultimo_claim"] = agora.strftime("%Y-%m-%d %H:%M:%S")
    salvar_dados(dados)
    await ctx.send("🎁 Você recebeu R$ 250 como VIP!")

@bot.command()
async def vipedit(ctx, *, emoji):
    dados = carregar_dados()
    uid = str(ctx.author.id)
    vip = dados["vips"].get(uid)
    if not vip:
        return await ctx.send("❌ Você não é VIP.")
    agora = datetime.now()
    if datetime.strptime(vip["expira_em"], "%Y-%m-%d %H:%M:%S") < agora:
        return await ctx.send("⛔ Seu VIP expirou.")
    dados["vips"][uid]["custom"] = emoji
    salvar_dados(dados)
    await ctx.send(f"✨ Emoji VIP atualizado: {emoji}")

from discord.ext.commands import cooldown, BucketType, CommandOnCooldown

@bot.command(name="daily")
@commands.cooldown(1, 86400, BucketType.user)
async def daily(ctx):
    recompensa = 500
    alterar_saldo(ctx.author.id, recompensa)
    registrar_transacao(ctx.author.id, "receita", recompensa, "Recompensa diária")
    embed = discord.Embed(
        title="🎁 Recompensa Diária Coletada!",
        description=f"{ctx.author.mention}, você recebeu **R$ {recompensa:,.2f}**.",
        color=0x00ffcc
    )
    embed.set_footer(text="Disponível novamente em 24 horas.")
    await ctx.send(embed=embed)

@bot.command(name="work")
@commands.cooldown(1, 3600, BucketType.user)
async def work(ctx):
    ganhos = random.randint(150, 300)
    alterar_saldo(ctx.author.id, ganhos)
    registrar_transacao(ctx.author.id, "receita", ganhos, "Salário do trabalho")
    embed = discord.Embed(
        title="💼 Você trabalhou!",
        description=f"{ctx.author.mention}, seu esforço rendeu **R$ {ganhos:,.2f}**.",
        color=0x2ecc71
    )
    embed.set_footer(text="Pode trabalhar novamente em 1 hora.")
    await ctx.send(embed=embed)

# Mensagem de cooldown personalizada
@daily.error
@work.error
async def cooldown_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        tempo = str(timedelta(seconds=int(error.retry_after)))
        embed = discord.Embed(
            title="⏳ Aguarde um pouco!",
            description=f"{ctx.author.mention}, você poderá usar este comando novamente em **{tempo}**.",
            color=0xffcc00
        )
        await ctx.send(embed=embed)

class WorkButtonView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="💼 Trabalhar", style=discord.ButtonStyle.green)
    async def work_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Esse botão não é pra você.", ephemeral=True)

        # Verificar cooldown
        comando = bot.get_command("work")
        try:
            await comando.invoke(await bot.get_context(interaction.message))
        except commands.CommandOnCooldown as error:
            tempo = str(timedelta(seconds=int(error.retry_after)))
            embed = discord.Embed(
                title="⏳ Aguarde!",
                description=f"{interaction.user.mention}, você poderá trabalhar novamente em **{tempo}**.",
                color=0xff9900
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.response.defer()

@bot.command(name="atm")
async def atm(ctx):
    saldo = saldo_usuario(ctx.author.id)
    dados = carregar_dados()
    vip = dados["vips"].get(str(ctx.author.id))
    emoji_vip = vip["custom"] if vip and vip["custom"] else "💰"

    embed = discord.Embed(
        title=f"{emoji_vip} Carteira de {ctx.author.name}",
        description=f"Saldo atual: **R$ {saldo:,.2f}**",
        color=0x3498db
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text="Use o botão abaixo para trabalhar!")

    view = WorkButtonView(ctx.author.id)
    await ctx.send(embed=embed, view=view)

@bot.command(name="bal")
async def bal(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    saldo = saldo_usuario(membro.id)

    embed = discord.Embed(
        title=f"📊 Saldo de {membro.name}",
        description=f"Saldo atual: **R$ {saldo:,.2f}**",
        color=0x95a5a6
    )
    embed.set_thumbnail(url=membro.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="rinha")
async def rinha(ctx, valor: str, max_jogadores: int):
    try:
        valor_num = int(parse_valor(valor))
        if valor_num <= 0 or max_jogadores < 2:
            return await ctx.send("❌ Valor e jogadores devem ser positivos. Mínimo de 2 jogadores.")
    except:
        return await ctx.send("❌ Formato inválido. Ex: brinha 10k 4")

    jogadores = []
    emojis = {}

    dados = carregar_dados()
    iniciado = False

    class RinhaView(View):
        def __init__(self):
            super().__init__(timeout=60)

        @discord.ui.button(label="Entrar na Rinha 🥊", style=discord.ButtonStyle.success)
        async def entrar(self, interaction: discord.Interaction, button: Button):
            nonlocal iniciado

            if iniciado:
                return await interaction.response.send_message("⛔ A rinha já começou!", ephemeral=True)

            user = interaction.user
            uid = str(user.id)

            if user.id in [j.id for j in jogadores]:
                return await interaction.response.send_message("⚠️ Você já entrou.", ephemeral=True)

            if saldo_usuario(uid) < valor_num:
                return await interaction.response.send_message("💸 Você não tem saldo suficiente.", ephemeral=True)

            jogadores.append(user)

            # Pega emoji VIP se tiver
            vip = dados["vips"].get(uid)
            if vip and vip.get("custom"):
                emojis[user.id] = vip["custom"]
            else:
                emojis[user.id] = random.choice(["🐸", "🐷", "🐵", "🐱", "🐶", "🐔", "🦊"])

            await interaction.response.send_message(f"✅ Você entrou na rinha! {emojis[user.id]}", ephemeral=True)
            await interaction.message.edit(content=f"💥 Rinha em andamento: {len(jogadores)}/{max_jogadores} jogadores", view=self)

            if len(jogadores) >= max_jogadores:
                await iniciar_rinha(interaction.message.channel)
                self.stop()

        @discord.ui.button(label="Finalizar Manualmente", style=discord.ButtonStyle.danger)
        async def finalizar(self, interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Apenas quem criou pode finalizar.", ephemeral=True)
            if len(jogadores) < 2:
                return await interaction.response.send_message("⚠️ Mínimo de 2 jogadores para iniciar.", ephemeral=True)
            await iniciar_rinha(interaction.message.channel)
            self.stop()

        async def on_timeout(self):
            if not iniciado:
                await ctx.send("⏳ A rinha expirou sem participantes suficientes.")

    async def iniciar_rinha(channel):
        nonlocal iniciado
        iniciado = True

        for j in jogadores:
            alterar_saldo(j.id, -valor_num)
            registrar_transacao(j.id, "despesa", valor_num, "Entrou na rinha")

        vencedor = random.choice(jogadores)
        premio_total = valor_num * len(jogadores)
        alterar_saldo(vencedor.id, premio_total)
        registrar_transacao(vencedor.id, "receita", premio_total, "Ganhou a rinha")

        emotes = [f"{emojis[j.id]} {j.display_name}" for j in jogadores]
        texto = "\n".join(emotes)

        await channel.send(f"🔥 Rinha finalizada!\n\n{texto}\n\n🏆 Vencedor: **{vencedor.mention}** ganhou **R$ {premio_total:,.2f}**!")

    embed = discord.Embed(
        title="🥊 Rinha de Emojis",
        description=f"{ctx.author.mention} iniciou uma rinha valendo **R$ {valor_num:,.2f}**!\nMáximo de jogadores: {max_jogadores}\n\nClique no botão para entrar!",
        color=0xe67e22
    )
    await ctx.send(embed=embed, view=RinhaView())

@bot.command(name="copo")
async def copo(ctx, valor: str):
    try:
        valor_num = int(parse_valor(valor))
    except:
        return await ctx.send("❌ Valor inválido. Ex: 10k, 1m...")

    if saldo_usuario(ctx.author.id) < valor_num:
        return await ctx.send("💸 Você não tem saldo suficiente.")

    copo_certo = random.randint(1, 3)

    class CopoView(View):
        def __init__(self):
            super().__init__(timeout=15)
            self.message = None

        async def reveal_result(self, interaction: discord.Interaction, escolhido: int):
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)

            if escolhido == copo_certo:
                alterar_saldo(ctx.author.id, valor_num)
                registrar_transacao(ctx.author.id, "receita", valor_num, "Acertou o copo")
                await interaction.followup.send(f"🥳 Parabéns {ctx.author.mention}! Você acertou e ganhou R$ {valor_num:,.2f}!")
            else:
                alterar_saldo(ctx.author.id, -valor_num)
                registrar_transacao(ctx.author.id, "despesa", valor_num, "Errou o copo")
                await interaction.followup.send(f"💔 Você errou, o copo certo era o **{copo_certo}**. Você perdeu R$ {valor_num:,.2f}.")

            self.stop()

        @discord.ui.button(label="1️⃣", style=discord.ButtonStyle.primary)
        async def copo1(self, interaction: discord.Interaction, button: Button):
            await self.reveal_result(interaction, 1)

        @discord.ui.button(label="2️⃣", style=discord.ButtonStyle.primary)
        async def copo2(self, interaction: discord.Interaction, button: Button):
            await self.reveal_result(interaction, 2)

        @discord.ui.button(label="3️⃣", style=discord.ButtonStyle.primary)
        async def copo3(self, interaction: discord.Interaction, button: Button):
            await self.reveal_result(interaction, 3)

        async def on_timeout(self):
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(content="⏰ Tempo esgotado! O jogo foi cancelado.", view=self)
            except:
                pass

    view = CopoView()
    msg = await ctx.send(f"🔍 Onde está o copo premiado, {ctx.author.mention}? Escolha abaixo!", view=view)
    view.message = msg

@bot.command(name="adicionar")
async def badicionar(ctx, membro: discord.Member = None, valor: str = None):
    if not eh_autorizado(ctx.author.id):
        return await ctx.send("⛔ Você não tem permissão para usar este comando.")

    if membro is None or valor is None:
        return await ctx.send("❌ Uso correto: `badicionar @usuário valor`")

    try:
        valor_num = int(parse_valor(valor))
    except:
        return await ctx.send("❌ Valor inválido. Use algo como `10k`, `1m`, etc.")

    alterar_saldo(membro.id, valor_num)
    registrar_transacao(membro.id, "receita", valor_num, f"Adicionado por {ctx.author.name}")
    await ctx.send(f"💰 {membro.mention} recebeu R$ {valor_num:,.2f}.")

@bot.command()
async def addgive(ctx, acao: str = None, membro: discord.Member = None):
    if not eh_autorizado(ctx.author.id):
        return await ctx.send("⛔ Você não tem permissão para isso.")

    if acao not in ["give", "remove"] or membro is None:
        return await ctx.send("❌ Uso correto: `baddgive give @usuário` ou `baddgive remove @usuário`")

    dados = carregar_dados()
    uid = str(membro.id)
    if "autorizados" not in dados:
        dados["autorizados"] = []

    if acao == "give":
        if uid in dados["autorizados"]:
            return await ctx.send("⚠️ Esse usuário já tem permissão.")
        dados["autorizados"].append(uid)
        await ctx.send(f"✅ {membro.mention} agora pode usar comandos de administração.")
    else:
        if uid not in dados["autorizados"]:
            return await ctx.send("⚠️ Esse usuário não tinha permissão.")
        dados["autorizados"].remove(uid)
        await ctx.send(f"🚫 Permissão removida de {membro.mention}.")

    salvar_dados(dados)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def block(ctx):
    canal = ctx.channel

    class ConfirmView(View):
        @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
        async def confirmar(self, interaction: discord.Interaction, button: Button):
            await canal.set_permissions(ctx.guild.default_role, send_messages=False)
            await interaction.response.edit_message(content="🔒 Canal bloqueado com sucesso!", view=None)

        @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
        async def cancelar(self, interaction: discord.Interaction, button: Button):
            await interaction.response.edit_message(content="❌ Cancelado.", view=None)

    await ctx.send("Deseja realmente bloquear o canal?", view=ConfirmView())

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    canal = ctx.channel

    class ConfirmView(View):
        @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.success)
        async def confirmar(self, interaction: discord.Interaction, button: Button):
            await canal.set_permissions(ctx.guild.default_role, send_messages=True)
            await interaction.response.edit_message(content="🔓 Canal desbloqueado com sucesso!", view=None)

        @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
        async def cancelar(self, interaction: discord.Interaction, button: Button):
            await interaction.response.edit_message(content="❌ Cancelado.", view=None)

    await ctx.send("Deseja realmente desbloquear o canal?", view=ConfirmView())

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, membro: discord.Member, *, motivo="Sem motivo"):
    class ConfirmView(View):
        @discord.ui.button(label="Confirmar Ban", style=discord.ButtonStyle.danger)
        async def confirmar(self, interaction: discord.Interaction, button: Button):
            await membro.ban(reason=motivo)
            await interaction.response.edit_message(content=f"✅ {membro} foi banido. Motivo: {motivo}", view=None)

        @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
        async def cancelar(self, interaction: discord.Interaction, button: Button):
            await interaction.response.edit_message(content="❌ Ban cancelado.", view=None)

    await ctx.send(f"Deseja banir {membro.mention}?", view=ConfirmView())

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    user = await bot.fetch_user(user_id)

    class ConfirmView(View):
        @discord.ui.button(label="Confirmar Unban", style=discord.ButtonStyle.success)
        async def confirmar(self, interaction: discord.Interaction, button: Button):
            await ctx.guild.unban(user)
            await interaction.response.edit_message(content=f"✅ {user} foi desbanido.", view=None)

        @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
        async def cancelar(self, interaction: discord.Interaction, button: Button):
            await interaction.response.edit_message(content="❌ Unban cancelado.", view=None)

    await ctx.send(f"Deseja desbanir `{user}`?", view=ConfirmView())

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, membro: discord.Member, tempo: int, *, motivo="Sem motivo"):
    class ConfirmView(View):
        @discord.ui.button(label="Confirmar Mute", style=discord.ButtonStyle.danger)
        async def confirmar(self, interaction: discord.Interaction, button: Button):
            duration = discord.utils.utcnow() + timedelta(minutes=tempo)
            await membro.timeout(until=duration, reason=motivo)
            await interaction.response.edit_message(content=f"🔇 {membro.mention} foi mutado por {tempo} minutos. Motivo: {motivo}", view=None)

        @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
        async def cancelar(self, interaction: discord.Interaction, button: Button):
            await interaction.response.edit_message(content="❌ Mute cancelado.", view=None)

    await ctx.send(f"Você quer mutar {membro.mention} por {tempo} minutos?", view=ConfirmView())

@bot.command()
@commands.has_permissions(manage_messages=True)
async def aviso(ctx, membro: discord.Member, *, motivo="Sem motivo"):
    await ctx.send(f"⚠️ {membro.mention} recebeu um aviso.\nMotivo: {motivo}")
    try:
        await membro.send(f"⚠️ Você foi avisado no servidor **{ctx.guild.name}**.\nMotivo: {motivo}")
    except:
        pass

@bot.command()
@commands.has_permissions(kick_members=True)
async def kickar(ctx, membro: discord.Member, *, motivo="Não informado"):
    view = View()

    async def confirmar(interaction):
        await membro.kick(reason=motivo)
        await interaction.response.edit_message(content=f"✅ {membro} foi expulso.\nMotivo: {motivo}", view=None)

    async def cancelar(interaction):
        await interaction.response.edit_message(content="❌ Ação cancelada.", view=None)

    view.add_item(Button(label="Confirmar", style=discord.ButtonStyle.danger, custom_id="confirma_kick"))
    view.add_item(Button(label="Cancelar", style=discord.ButtonStyle.secondary, custom_id="cancelar_kick"))

    msg = await ctx.send(f"Deseja realmente **expulsar {membro}**?", view=view)

    async def wait_buttons():
        interaction = await bot.wait_for(
            "interaction",
            check=lambda i: i.user == ctx.author and i.message.id == msg.id,
            timeout=30
        )
        if interaction.data["custom_id"] == "confirma_kick":
            await confirmar(interaction)
        else:
            await cancelar(interaction)

    bot.loop.create_task(wait_buttons())

@bot.command(name="bajuda")
async def bajuda(ctx):
    embed = discord.Embed(title="📘 Menu de Ajuda", description="Escolha uma categoria no menu abaixo.", color=0x2b2d31)
    await ctx.send(embed=embed, view=AjudaView())
from discord import SelectOption, ui

class AjudaSelect(ui.Select):
    def __init__(self):
        options = [
            SelectOption(label="Administração", description="Comandos de moderação", emoji="🛠️", value="admin"),
            SelectOption(label="Economia", description="Comandos de dinheiro", emoji="💰", value="eco"),
            SelectOption(label="Diversão", description="Comandos divertidos", emoji="🎉", value="fun"),
        ]
        super().__init__(placeholder="Selecione uma categoria...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "admin":
            embed = discord.Embed(title="🛠️ Comandos de Administração", color=0x2b2d31)
            embed.add_field(name="`lock`", value="Trava um canal", inline=False)
            embed.add_field(name="`unlock`", value="Destrava um canal", inline=False)
            embed.add_field(name="`ban`", value="Bane um membro com confirmação", inline=False)
            embed.add_field(name="`unban`", value="Desbane um membro por ID", inline=False)
            embed.add_field(name="`mute`", value="Silencia um membro", inline=False)
            embed.add_field(name="`kickar`", value="Expulsa um membro com confirmação", inline=False)
            embed.add_field(name="`aviso`", value="Avisa um membro", inline=False)

        elif self.values[0] == "eco":
            embed = discord.Embed(title="💰 Comandos de Economia", color=0x2b2d31)
            embed.add_field(name="`bdaily`", value="Coleta diária", inline=False)
            embed.add_field(name="`bwork`", value="Trabalhar e ganhar dinheiro", inline=False)
            embed.add_field(name="`batm` / `bbal`", value="Consulta seu saldo", inline=False)
            embed.add_field(name="`bcopo <valor>`", value="Jogo de adivinhar o copo", inline=False)
            embed.add_field(name="`brinha <valor> <jogadores>`", value="Inicia uma rinha de emojis", inline=False)

        elif self.values[0] == "fun":
            embed = discord.Embed(title="🎉 Comandos de Diversão", color=0x2b2d31)
            embed.add_field(name="(em breve)", value="Mais comandos virão aqui!", inline=False)

        await interaction.response.edit_message(embed=embed, view=self.view)

class AjudaView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AjudaSelect())


import discord
from discord.ext import commands
import random
import json
import asyncio

# Funções utilitárias (ajuste conforme sua estrutura)
def carregar_dados():
    with open("financas.json", "r") as f:
        return json.load(f)

def salvar_dados(dados):
    with open("financas.json", "w") as f:
        json.dump(dados, f, indent=2)

def get_saldo(uid):
    dados = carregar_dados()
    return dados["usuarios"].get(str(uid), {}).get("saldo", 0)

def alterar_saldo(uid, valor, tipo, descricao):
    dados = carregar_dados()
    uid = str(uid)
    if uid not in dados["usuarios"]:
        dados["usuarios"][uid] = {"saldo": 0, "transacoes": []}
    dados["usuarios"][uid]["saldo"] += valor
    dados["usuarios"][uid]["transacoes"].append({
        "tipo": "receita" if valor > 0 else "despesa",
        "valor": abs(valor),
        "descricao": descricao,
        "data": str(discord.utils.utcnow())[:19]
    })
    salvar_dados(dados)

def get_emoji(uid, padrao):
    dados = carregar_dados()
    if str(uid) in dados.get("vips", {}) and dados["vips"][str(uid)].get("emoji"):
        return dados["vips"][str(uid)]["emoji"]
    aleatorios = ["🐶", "🐱", "🦊", "🐵", "🐸", "🧙", "🤖", "👻", "😈", "💀", "👽", "🧛"]
    return random.choice(aleatorios)

# Comando
@bot.command(name="bet")
async def bbet(ctx, membro: discord.Member, valor: int):
    autor = ctx.author
    if membro.bot or membro.id == autor.id:
        return await ctx.reply("Mencione um usuário válido que não seja você nem um bot.")

    if valor <= 0:
        return await ctx.reply("Informe um valor válido para aposta.")

    if get_saldo(autor.id) < valor:
        return await ctx.reply("Você não tem saldo suficiente para essa aposta.")
    if get_saldo(membro.id) < valor:
        return await ctx.reply(f"{membro.mention} não tem saldo suficiente para essa aposta.")

    emoji_autor = get_emoji(autor.id, "👤")
    emoji_membro = get_emoji(membro.id, "👥")

    class AceitarView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.aceitou = False

        @discord.ui.button(label="Aceitar Aposta", style=discord.ButtonStyle.success)
        async def aceitar(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != membro.id:
                return await interaction.response.send_message("Somente o desafiado pode aceitar.", ephemeral=True)

            self.aceitou = True
            self.stop()

            resultado = random.choice(["cara", "coroa"])
            vencedor = autor if resultado == "cara" else membro
            perdedor = membro if vencedor == autor else autor

            alterar_saldo(vencedor.id, valor, "receita", f"Venceu aposta cara ou coroa contra {perdedor.name}")
            alterar_saldo(perdedor.id, -valor, "despesa", f"Perdeu aposta cara ou coroa para {vencedor.name}")

            await interaction.response.edit_message(content=f"🪙 A moeda caiu em **{resultado}**!\n🏆 {vencedor.mention} venceu e ganhou **{valor} moedas**!", view=None)

        async def on_timeout(self):
            for item in self.children:
                item.disabled = True
            try:
                await msg.edit(content="⏰ Tempo esgotado para aceitar a aposta.", view=self)
            except:
                pass

    embed = discord.Embed(title="🎲 Aposta: Cara ou Coroa",
                          description=f"{emoji_autor} {autor.mention} desafiou {emoji_membro} {membro.mention} para uma aposta de **{valor} moedas**!\n\nClique em **Aceitar Aposta** para jogar cara ou coroa.",
                          color=discord.Color.orange())
    msg = await ctx.send(embed=embed, view=AceitarView())

bot.run("MTM2NTM4NTg0NjgyNzUxNTkwNA.GDX5SH.TvZ7HM-dmI0V5of6aEjmQev1uD3axh-5JmT3Go")
