import builtins as sm

from utils import Ctx, Param, esc, to_hms, from_hms, ansiesc_remove
from inspect import signature
from disnake import ApplicationCommandInteraction, Guild, TextChannel, VoiceChannel
from disnake.errors import ClientException, NotFound, Forbidden

from resolve import resolve, Entry
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

from player import Player
from re import compile, Pattern
from operator import add, sub

from asyncio import sleep

from typing import Callable, Awaitable, Literal



class Queue(list[Entry]):
    def __init__(self):
        super().__init__()

        self.history: list[Entry] = []

    def __len__(self) -> int: return super().__len__() - 1

    def pop(self, i: int = 0, tohistory: bool = False) -> Entry:
        ret = super().pop(i)

        if tohistory: self.history.insert(0, ret)

        return ret

    def clear(self): del self[1:]

    def skip(self, i: int, tohistory: bool = False) -> list[Entry]: return [self.pop(tohistory = tohistory) for _ in range(i)]
class AssignValue:
    loop: Literal[False, 'entry', 'queue'] = False

    def __init__(self, last: TextChannel):
        self.queue: Queue = Queue()

        self.player: Player = Player()

        self.last: TextChannel = last
class Assign(dict[Guild, AssignValue]):
    def __getitem__(self, ctx: Ctx) -> AssignValue: return super().__getitem__(ctx.guild)


    def init(self, ctx: Ctx): self[ctx.guild] = AssignValue(
        super().__getitem__(ctx.guild).last if ctx.guild in self else ctx.channel
    )

    def cleanup(self, ctx: Ctx, disconnect: bool = True):
        self.init(ctx)


        if disconnect: sm.client.loop.create_task(
            ctx.voice_client.disconnect()
        )
sm.assign = Assign()

sm.spotify = Spotify(client_credentials_manager = SpotifyClientCredentials(*sm.config['spotify']))


sm.commands = set()
def command(
    description: str,
    emote: str,
    alias: str | None = None,
) -> Callable[
    [Callable[[Ctx, Param, ...], Awaitable[None]]], None
]:
    def command_(coro: Callable[[Ctx, Param, ...], Awaitable[None]]):
        # (name, aliases), (coroutine, arguments - (default value as Param instance, name), emote, description)
        sm.commands.add((
            (
                coro.__name__[:-2],
                *((alias,) if alias else ())
            ),
            (
                coro,
                tuple(
                    (
                        x.default,
                        x.name[:-1]
                    ) for x in signature(coro).parameters.values()
                )[1:],
                emote,
                description
            )
        ))

    return command_

async def invoke_command(ctx: Ctx):
    for x, y in sm.commands:
        if ctx.invoke[0] in x:
            ctx.invoke = (x[0], ctx.invoke[1])

            if ctx.guild not in sm.assign:
                sm.assign.init(ctx)
            else:
                sm.assign[ctx].last = ctx.channel


            ctx.emote = y[2]

            await y[0](
                ctx,

                *(
                    z.inst(
                        ctx.invoke[1][i] if not z.wide else ' '.join(ctx.invoke[1][i:])
                    ) for i, z in enumerate(
                        w[0] for w in y[1][:len(ctx.invoke[1])]
                    )
                )
            )



            return
sm.invoke_command = invoke_command

async def check_command(flags: set[Literal['on_channel', 'is_playing', 'dj', 'mod']], ctx: Ctx) -> bool:
    if 'on_channel' in flags and not ctx.author.voice:
        await ctx.error('You must be connected to any voice channel.'); return False
    if 'is_playing' in flags and not sm.assign[ctx].player.channel:
        await ctx.error('I must be playing anything.'); return False
    if 'on_channel' in flags and 'is_playing' in flags and ctx.author.voice.channel != sm.assign[ctx].player.channel:
        await ctx.error("I'm already connected to another voice channel."); return False

    if not ctx.perms.manage_messages:
        if 'mod' in flags:
            await ctx.error('You need a **_MANAGE\_MESSAGES_** permission to use this command.'); return False
        elif sm.settings[ctx.guild]['dj_role'] not in {x.id for x in ctx.roles} - {ctx.guild.id} and not (sm.settings[ctx.guild]['dj_role'] == ctx.guild.id and not sm.settings[ctx.guild]['voting']) and not ctx.enforce_dj:
            if 'dj' in flags:
                if not sm.settings[ctx.guild]['voting']:
                    await ctx.error(f'You need a <@&{ctx.guild.get_role(sm.settings[ctx.guild]["dj_role"]).id}> role to use this command.'); return False
                elif len({x for x in sm.assign[ctx].player.channel.members if not x.bot}) > 1:
                    if (votes := sm.assign[ctx].queue[0].voting(ctx)) > 0:
                        await ctx.voting(
                            f'**_{votes}_** more vote{"s are" if votes > 1 else " is"} required to invoke this command.'
                        )

                    return False
        elif sm.assign[ctx].player.channel:
            for x in {*voting[0]} if (voting := sm.assign[ctx].queue[0].voting_) else ():
                if x == ctx.invoke: del voting[0][x]
    elif sm.assign[ctx].player.channel:
        for x in {*voting[0]} if (voting := sm.assign[ctx].queue[0].voting_) else ():
            if x == ctx.invoke: del voting[0][x]


    return True

@command(
    'Adds an entry from the specified source to the queue.',
    '▶',
    'p'
)
async def play__(
    ctx: Ctx,

    source_: Param = Param(
        3,
        True,
        wide = True
    )
):
    source = source_.eq()


    if not await check_command({
        'on_channel'
    }, ctx): return

    elif source is False: await ctx.error('You must provide valid source (search query or URL).'); return



    if type(ctx.ctx) is ApplicationCommandInteraction: await ctx.defer()

    try:
        ret = await resolve(source, ctx.author)
    except Exception as ex:
        await ctx.error(
f'''Unable to extract requested source info, details:
{esc(ansiesc_remove(str(ex)), trunc_ = 150)}'''
        ); return


    if type(ret) is Entry:
        sm.assign[ctx].queue.append(ret)


        if sm.assign[ctx].queue: await ctx.info(
            f'Added an **_entry_** to the queue at position **_{len(sm.assign[ctx].queue)}_**:',
            ret.embed(False)
        )
    else:
        sm.assign[ctx].queue.extend(ret.entries)


        await ctx.info(
            'Added an **_playlist_** to the queue:',
            ret.embed(False)
        )


    if not sm.assign[ctx].player.channel:
        sm.assign[ctx].player.channel = ctx.author.voice.channel

        try:
            await sm.assign[ctx].player.channel.connect()
        except (ClientException, NotFound, Forbidden): ...


        while sm.assign[ctx].queue != []:
            if not sm.assign[ctx].queue[0].direct:
                try:
                    sm.assign[ctx].queue[0] = await resolve(
                        q0.url if not (q0 := sm.assign[ctx].queue[0]).spotify else f'ytsearch:{q0.uploader[0]} - {q0.title}',

                        q0.requested_by, q0.playlist, True
                    )
                except Exception as ex:
                    await ctx.error(
f'''Unable to extract queue entry info, details:
{esc(ansiesc_remove(str(ex)), trunc_ = 150)}'''
                    )


                    if not ctx.voice_client:
                        sm.assign.cleanup(ctx, False); return
                    else:
                        sm.assign[ctx].queue.pop()

                        if sm.assign[ctx].loop == 'entry': sm.assign[ctx].loop = False


                        continue


            if sm.assign[ctx].loop != 'entry':
                await ctx.info(
                    'Now playing:',
                    sm.assign[ctx].queue[0].embed()
                )


            effects = len(sm.settings[ctx.guild]['effects'])
            ctx.voice_client.play(
                sm.assign[ctx].player.play((q0 := sm.assign[ctx].queue[0]).direct, q0.start_time, q0.playlist_type)
            )

            alone = 0
            while getattr(ctx.voice_client, 'is_playing', lambda: False)():
                try:
                    if not {x for x in sm.assign[ctx].player.channel.members if not x.bot}:
                        alone += 0.333
                        if alone > 10:
                            sm.assign.cleanup(ctx)


                            await ctx.error('I was alone on the voice channel for 10 seconds, so I disconnected.'); return
                    else:
                        alone = 0
                except AttributeError: ...

                if sm.assign[ctx].player.channel != ctx.voice_client.channel:
                    sm.assign[ctx].player.channel = ctx.voice_client.channel

                    await ctx.voice_client.disconnect(force = True)
                    nvc = await sm.assign[ctx].player.channel.connect()
                    nvc.play(
                        sm.assign[ctx].player.play_()
                    )

                if effects != (len_ := len(sm.settings[ctx.guild]['effects'])):
                    effects = len_

                    sm.assign[ctx].player.play_()


                await sleep(0.333)
            else:
                if sm.assign[ctx].queue != []:
                    if ctx.voice_client:
                        if sm.assign[ctx].loop != 'queue':
                            sm.assign[ctx].queue.pop(tohistory = True)
                        else:
                            sm.assign[ctx].queue.append(
                                sm.assign[ctx].queue.pop()
                            )
                    else:
                        sm.assign.cleanup(ctx, False)


                        await ctx.error('I was kicked out of the voice channel.'); return
                else: return
        else:
            sm.assign.cleanup(ctx)


            await ctx.complete('Playback complete.')

@command(
    'Stops playback.',
    '⏹',
    'st'
)
async def stop__(
    ctx: Ctx
):
    if not await check_command({
        'on_channel',
        'is_playing',
        'dj'
    }, ctx): return



    await ctx.info(
        'Playback stopped at:',
        sm.assign[ctx].queue[0].embed()
    )


    sm.assign.cleanup(ctx)

@command(
    'Skips specified number of entries (default: 1).',
    '⏭',
    's'
)
async def skip__(
    ctx: Ctx,

    entries_: Param = Param(
        4,
        False,
        1
    )
):
    entries = entries_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if not sm.assign[ctx].queue: await ctx.error('The queue is empty.')
    elif entries in range(1, (len_ := len(sm.assign[ctx].queue)) + 1):
        if not await check_command({'dj'}, ctx): return



        if sm.assign[ctx].loop == 'entry': sm.assign[ctx].loop = False


        await ctx.info(
            f'Skipped {f"an **_entry_**:" if (entries_ := entries == 1) else f"**_{entries}_** entries to:"}',
            sm.assign[ctx].queue[0 if entries_ else entries].embed()
        )


        if sm.assign[ctx].loop != 'queue':
            sm.assign[ctx].queue.skip(entries, True)
        else:
            sm.assign[ctx].queue.extend(sm.assign[ctx].queue.skip(entries))

        ctx.voice_client.stop()
    else:
        await ctx.error(f'You must provide valid number of queue entries to skip **(1 - {len_})**.')

TIMESTAMP: tuple[Pattern, Pattern] = (
    compile('^[+-]?(([1-9][0-9]*:[0-5][0-9])|([0-5]?[0-9])):[0-5][0-9]$'),
    compile('^-?[1-9][0-9]*[smh]$')
)
@command(
    'Rewinds the currently played track to specified timestamp.',
    '⏩',
    'ss'
)
async def seek__(
    ctx: Ctx,

    timestamp_: Param = Param(
        3,
        False
    )
):
    timestamp = timestamp_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if not TIMESTAMP[0].match(sm.assign[ctx].queue[0].duration):
        await ctx.error('Unable to invoke this command because of unsupported duration of the currently played track :(')

    elif timestamp is None:
        await ctx.info(f'Current timestamp: **_{to_hms(sm.assign[ctx].player.elapsed)}_ / _{sm.assign[ctx].queue[0].duration}_**.')

    else:
        if t := getattr(TIMESTAMP[0].match(timestamp), 'group', lambda: None)():
            if not await check_command({'dj'}, ctx): return



            if t[0] in {'+', '-'}:
                s = (add if t[0] == '+' else sub)(sm.assign[ctx].player.elapsed, from_hms(t[1:]))

                if 0 < s < from_hms(sm.assign[ctx].queue[0].duration):
                    sm.assign[ctx].player.elapsed = s


                    await ctx.info(f'Rewinded by **_{t}_**.')
                else:
                    await ctx.error('Provided timestamp is invalid.')
            else:
                s = from_hms(t)

                if s < from_hms(sm.assign[ctx].queue[0].duration):
                    sm.assign[ctx].player.elapsed = s


                    await ctx.info(f'Seeked to **_{t}_**.')
                else:
                    await ctx.error('Provided timestamp is invalid.')

            sm.assign[ctx].player.play_()

        else:
            if t := getattr(TIMESTAMP[1].match(timestamp), 'group', lambda: None)():
                if not await check_command({'dj'}, ctx): return



                s = sm.assign[ctx].player.elapsed + int(t[:-1]) * 1 if t[-1] == 's' else 60 if t[-1] == 'm' else 3600

                if 0 < s < from_hms(sm.assign[ctx].queue[0].duration):
                    sm.assign[ctx].player.elapsed = s


                    await ctx.info(f'Rewinded by **_{t}_**.')
                else:
                    await ctx.error('Provided timestamp is invalid.')


                sm.assign[ctx].player.play_()
            else:
                await ctx.error('You must provide valid timestamp (ex. `2m`, `-5:15`, `+3:15`, `-230s`).')

@command(
    'Loops the currently played track / entrire queue.',
    '🔁',
    'l'
)
async def loop__(
    ctx: Ctx,

    loop_: Param = Param(
        3,
        False,
        'entry',
        ('entry', 'queue')
    )
):
    loop = loop_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if loop is not False:
        if not await check_command({'dj'}, ctx): return



        if loop != sm.assign[ctx].loop:
            sm.assign[ctx].loop = loop


            await ctx.info(
f'''Use the same command to break the looping.

Looping {f'an **_entry_**:' if (loop_ := loop == 'entry') else 'the **_entire queue_**.'}''',
                *((sm.assign[ctx].queue[0].embed(),) if loop_ else ())
            )
        else:
            await ctx.info(
                f'{f"An **_entry_**" if (loop_ := loop == "entry") else "The **_queue_**"} is no longer looped.',
                *((sm.assign[ctx].queue[0].embed(),) if loop_ else ())
            )


            sm.assign[ctx].loop = False
    else:
        await ctx.error("You must provide **_'entry'_** or **_'queue'_** as argument _(default: 'entry')_.")

@command(
    'Moves the bot to specified channel.',
    '⤵',
    'ch'
)
async def chmove__(
    ctx: Ctx,

    ch_: Param = Param(
        7,
        True
    )
):
    ch = ch_.eq(ctx.guild)


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if ch == ctx.voice_client.channel:
        await ctx.error('The bot is already on this channel.')
    elif type(ch) is VoiceChannel:
        if not await check_command({'dj'}, ctx): return



        await ctx.voice_client.move_to(ch)


        await ctx.info(f'Moved the bot to: <#{ch.id}>.')
    else:
        await ctx.info(f'You must provide a valid voice channel (by mentioning it).')

@command(
    'Shows the queue preview.',
    '',
    'q'
)
async def queue__(
    ctx: Ctx,

    page_: Param = Param(
        4,
        False,
        1
    )
):
    page = page_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if not (entries := [*enumerate(sm.assign[ctx].queue)][1:]):
        await ctx.info(
'''The queue is empty.

▶ Now playing:''',
            sm.assign[ctx].queue[0].embed()
        )
    else:
        if page in range(1, (len_ := len(pages := [entries[i:i + 12] for i in range(0, len(entries), 12)])) + 1):
            embed = ctx.embed(
f"""{f'''_Use **{esc(f'{sm.settings[ctx.guild]["prefix"]}queue')}**_ **(2 - {len_})** _to see other pages._

''' if page == 1 else ''}{f'Page **_{page}_**:'}""",
                0x0000A0, '📄', None
            )
            for x, y in pages[page - 1]:
                embed.add_field(
                    x,
                    (
                        entry :=
f'''**Title**: ￼
**Duration**: {y.duration}
**Requested by**: {y.requested_by.name}#{y.requested_by.discriminator}'''
                    ).replace(
                        '￼',
                        esc(y.title, y.url, maxlen = 1025 - len(entry)),
                        1
                    ),
                    inline = False
                )

                if (download := esc('download', y.direct, retfalse = True)) if y.direct else False:
                    embed.add_field(
                        '​',
                        download,
                        inline = False
                    )


            await ctx.send(embed); await ctx.info('▶ Now playing:', sm.assign[ctx].queue[0].embed())
        else:
            await ctx.error(f'You must provide valid queue preview page index **(1 - {len_})** _(default: 1)_.')

@command(
    'Clears the queue.',
    '🗑',
    'c'
)
async def clear__(
    ctx: Ctx
):
    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if sm.assign[ctx].queue:
        if not await check_command({'dj'}, ctx): return



        sm.assign[ctx].queue.clear()


        await ctx.info('Purged the queue.')
    else:
        await ctx.error('Queue is already empty.')

@command(
    'Removes an entry from the queue.',
    '🗑',
    'r'
)
async def remove__(
    ctx: Ctx,

    entry_: Param = Param(
        4,
        True
    )
):
    entry = entry_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if not sm.assign[ctx].queue: await ctx.error('The queue is empty.')
    elif entry in range(1, (len_ := len(sm.assign[ctx].queue)) + 1):
        if not await check_command({'dj'}, ctx): return



        await ctx.info(
            f'Removed an **_entry_** from position **_{entry}_**:',
            sm.assign[ctx].queue[entry].embed()
        )


        sm.assign[ctx].queue.pop(entry)
    else:
        await ctx.error(f'You must provide valid queue entry position to remove **(1 - {len_})**.')

@command(
    'Moves an queue entry to the specified position.',
    '',
    'm'
)
async def move__(
    ctx: Ctx,

    from_: Param = Param(
        4,
        True
    ),
    to_: Param = Param(
        4,
        True
    )
):
    from__ = from_.eq()
    to__ = to_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if not sm.assign[ctx].queue: await ctx.error('The queue is empty.')
    elif from__ in (range_ := range(1, len(sm.assign[ctx].queue) + 1)) and to__ in range_ and from__ != to__:
        if not await check_command({'dj'}, ctx): return



        sm.assign[ctx].queue.insert(to__, sm.assign[ctx].queue.pop(from__))


        await ctx.info(
            f'Moved an entry to position {to__}:',
            sm.assign[ctx].queue[to__].embed()
        )
    else:
        await ctx.error('You must provide two valid queue positions.')

@command(
    'Changes the audio volume.',
    '📢',
    'v'
)
async def volume__(
    ctx: Ctx,

    volume_: Param = Param(
        4,
        False
    )
):
    volume = volume_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return



    if volume is None:
        await ctx.info(f'Current volume: **_{sm.settings[ctx.guild]["volume"]}%_**.')

    elif volume in range(201):
        if not await check_command({'dj'}, ctx): return



        sm.settings[ctx.guild]['volume'] = volume


        await ctx.info(f'Volume set to **_{volume}%_**.')
    else:
        await ctx.error(f'You must provide valid volume percentage value **(0 - 200)**.')

@command(
    'Adds or removes specified audio effects.',
    '🎼',
    'e'
)
async def effect__(
    ctx: Ctx,

    effect_: Param = Param(
        3,
        False,
        choices = (*sm.config['effects'], 'clear')
    )
):
    effect = effect_.eq()


    if not await check_command({
        'on_channel',
        'is_playing'
    }, ctx): return

    elif effect is False:
        await ctx.error(f'You must provide valid effect **(available: {", ".join(f"`{x}`" for x in sm.config["effects"])})**.'); return



    if effect is None:
        await ctx.info(
f'''Current effects: {', '.join(f'**_{x}_**' for x in sm.settings[ctx.guild]['effects']) if sm.settings[ctx.guild]['effects'] else '**_None_**'}
{f"""
Available:
**{', '.join(f'`{x}`' for x in sm.config['effects'] if x not in sm.settings[ctx.guild]['effects'])}**""" if len(sm.config['effects']) - len(sm.settings[ctx.guild]['effects']) else ''}{f"""
_Use **{esc(sm.settings[ctx.guild]['prefix'])}effect clear** to clear toggled effects._""" if sm.settings[ctx.guild]['effects'] else ''}'''
        )


    elif not await check_command({'dj'}, ctx): return

    elif effect == 'clear':
        sm.settings[ctx.guild]['effects'].clear()


        await ctx.info('Effects cleared.')
    elif effect not in sm.settings[ctx.guild]['effects']:
        sm.settings[ctx.guild]['effects'].add(effect)


        await ctx.info(f'Added **_{effect}_** effect.')
    else:
        sm.settings[ctx.guild]['effects'].remove(effect)


        await ctx.info(f'Removed **_{effect}_** effect.')

@command(
    'Sets the command prefix.',
    '⚙'
)
async def prefix__(
    ctx: Ctx,

    prefix_: Param = Param(
        3,
        False
    )
):
    prefix = prefix_.eq()



    if prefix is None:
        await ctx.setting(f'Current prefix: **_{esc(sm.settings[ctx.guild]["prefix"])}_**.')

    else:
        if not await check_command({
            'mod'
        }, ctx): return



        sm.settings[ctx.guild]['prefix'] = prefix[:5]


        await ctx.setting(f'Prefix set to: **_{esc(sm.settings[ctx.guild]["prefix"])}_**.')

@command(
    'Sets the DJ role.',
    '⚙'
)
async def dj__(
    ctx: Ctx,

    dj_: Param = Param(
        8,
        False
    )
):
    dj = dj_.eq(ctx.guild)



    if dj is None:
        await ctx.setting(f'Current DJ role: <@&{sm.settings[ctx.guild]["dj_role"]}>.')

    elif dj is not False:
        if not await check_command({
            'mod'
        }, ctx): return



        sm.settings[ctx.guild]['dj_role'] = dj.id


        await ctx.setting(f'DJ role set to: <@&{sm.settings[ctx.guild]["dj_role"]}>.')
    else:
        await ctx.error('You must provide a valid role (by mentioning it).')


@command(
    'Toggles the voting on using DJ commands for members without this role.',
    '⚙'
)
async def voting__(
    ctx: Ctx
):
    if not await check_command({
        'mod'
    }, ctx): return



    sm.settings[ctx.guild]['voting'] = not sm.settings[ctx.guild]['voting']


    await ctx.setting(f'Toggled **_{"ON" if sm.settings[ctx.guild]["voting"] else "OFF"}_** the voting on using DJ commands for non-DJ members.')