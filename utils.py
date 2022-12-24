import builtins as sm

from disnake import Option, Embed, Message, ApplicationCommandInteraction, Guild, VoiceClient, TextChannel, Member, Permissions, Role, VoiceChannel
from disnake.errors import NotFound, Forbidden

from copy import deepcopy

from re import compile, Pattern

from typing import Literal, Callable



class Ctx:
    def __init__(self, ctx: Message | ApplicationCommandInteraction, invoke: tuple[str, tuple[str | int | TextChannel | VoiceChannel | Role, ...]]):
        self.ctx: Message | ApplicationCommandInteraction = ctx
        self.invoke: tuple[str, tuple[str | int | TextChannel | VoiceChannel | Role, ...]] = invoke
        self.emote: str | None = None
        self.enforce_dj: bool = False
        self.guild: Guild = ctx.guild
        self.channel: TextChannel = ctx.channel
        self.author: Member = ctx.author
        self.perms: Permissions = ctx.author.guild_permissions
        self.roles: list[Role] = ctx.author.roles
        self.response: list[bool] = [False, False]
    @property
    def voice_client(self) -> VoiceClient | None: return self.guild.voice_client


    async def send(self, embed: Embed):
        if self.response[0]:
            try:
                await self.channel.send(embed = embed)
            except NotFound:
                try:
                    await sm.assign[self].last.send(embed = embed)
                except (NotFound, Forbidden): ...
            except Forbidden: ...
        else:
            self.response[0] = True

            try:
                if type(self.ctx) is not Message:
                    if not (self.response[1] or self.ctx.response.is_done()):
                        await self.ctx.response.send_message(embed = embed)
                    else:
                        await self.ctx.followup.send(embed = embed)
                else:
                    await self.ctx.reply(embed = embed)
            except (NotFound, Forbidden): ...

    async def defer(self):
        self.response[1] = True

        try:
            await self.ctx.response.defer()
        except Forbidden: ...


    def embed(self, content: str, colour: int, emote: str, process: Callable[[Embed], Embed] | None) -> Embed:
        (embed := Embed(colour = colour, description = f'{emote} {content}')).set_author(name = sm.client.user.name, icon_url = sm.client.user.avatar.url)
        if not self.response[0]:
            embed.set_footer(text = f'{self.invoke[0]} ⸺ invoked by {self.author.name}#{self.author.discriminator}')

        return embed if not process else process(embed)

    async def error(self, content: str, process: Callable[[Embed], Embed] | None = None): await self.send(self.embed(content, 0xFF0000, '❌', process))
    async def info(self, content: str, process: Callable[[Embed], Embed] | None = None): await self.send(self.embed(content, 0x009BFF, self.emote, process))
    async def voting(self, content: str): await self.send(self.embed(content, 0x4F00AD, '🗳️', None))
    async def setting(self, content: str): await self.send(self.embed(content, 0x636363, self.emote, None))
    async def complete(self, content: str, process: Callable[[Embed], Embed] | None = None): await self.send(self.embed(content, 0x69FF00, '✅', process))

ROLE: Pattern = compile(r'<@&(\d{17,})>')
CH: Pattern = compile(r'<#(\d{17,})>')
class Param:
    def __init__(
        self,

        type_: Literal[3, 4, 7, 8],
        required: bool,
        value: str | int | TextChannel | VoiceChannel | Role | None = None,
        choices: tuple[str, ...] | None = None,
        wide: bool = False
    ):
        self.type_: Literal[3, 4, 7, 8] = type_
        self.required: bool = required
        self.value: str | int | TextChannel | VoiceChannel | Role | None = value
        self.choices: tuple[str, ...] | None = choices
        self.wide: bool = wide

    def inst(self, value: str | int | TextChannel | VoiceChannel | Role | None = None): return (
        inst := deepcopy(self),
        setattr(inst, 'value', value)
    )[0]

    def eq(self, g: Guild | None = None) -> str | int | TextChannel | VoiceChannel | Role | Literal[False, None]:
        if self.value is None:
            return self.value if not self.required else False
        match self.type_:
            case 3:
                return self.value if (
                    (self.value in self.choices) if self.choices else True
                ) else False
            case 4:
                try:
                    return int(self.value)
                except ValueError: return False
            case 7:
                if not isinstance(self.value, TextChannel | VoiceChannel):
                    return ch if (
                        (ch := g.get_channel(int(ch_.group(1)))) if (ch_ := CH.match(self.value)) else False
                    ) else False
                else: return self.value
            case 8:
                if type(self.value) is not Role:
                    return role if (
                        (role := g.get_role(int(role_.group(1)))) if (role_ := ROLE.match(self.value)) else False
                    ) else g.default_role if self.value == '@everyone' else False
                else: return self.value

    def option(self, name: str) -> Option: return Option(
        name,
        type = self.type_,
        required = self.required,
        choices = self.choices
    )

def trunc(content: str, length: int) -> str: return content if len(content) <= length else f'{content[:length].rstrip()}…'
ESC: Pattern = compile(r'([*_`~><()\[\]\\]|@everyone)')
def esc_(content: str) -> str: return ESC.sub(
    lambda m: f'{chr(92)}{m_ if (m_ := m.group(0)) not in {"[", "]"} else "(" if m_ == "[" else ")"}',
    content
)
def esc(
    content: str,
    url: str | None = None,
    trunc_: int = 50,
    maxlen: int = 1024,
    retfalse: bool = False
) -> str | Literal[False]: return (
    content_ := esc_(trunc(content, trunc_)),

    f'[{content_}]({url_})' if (len(url_ := esc_(url)) + len(content_) + 4 <= maxlen if url else False) else content_ if not retfalse else False
)[1]

def to_hms(s: float) -> str:
    m, s = divmod(int(s + 0.5), 60)
    h, m = divmod(m, 60)

    return ':'.join((
        *((str(h),) if h else ()),
        (
            m_ := str(m),

            m_ if not h else m_.zfill(2)
        )[1],
        str(s).zfill(2)
    ))
def from_hms(hms: str) -> int:
    t = [int(x) for x in hms.split(':')]

    return sum((
        t.pop(-1),
        t.pop(-1) * 60,
        *((t.pop(-1) * 3600,) if t else ())
    ))

ANSIESC: Pattern = compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
def ansiesc_remove(content: str) -> str: return ANSIESC.sub('', content)