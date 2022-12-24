import builtins as sm

from yt_dlp import YoutubeDL
from threading import Thread
from ctypes import pythonapi, c_ulong, py_object
from time import perf_counter
from asyncio import sleep

from re import compile, Pattern

from subprocess import run, PIPE, DEVNULL
from json import loads

from utils import to_hms, esc, Ctx
from disnake import Embed, Member, Message, ApplicationCommandInteraction, TextChannel, VoiceChannel, Role

from time import sleep as tsleep

from typing import Callable



PLS: Pattern = compile(r'File\d+=(.+)(?=\n| |$)')
M3U: Pattern = compile('^(?!#)(.+)')


class Entry:
    def __init__(self, entry: dict, requested_by: Member, playlist: object | None = None):
        self.title: str = entry.get('title', 'Unknown title')
        self.duration: str = to_hms(duration) if isinstance(duration := entry.get('duration', 'Unknown duration'), float | int) else duration
        self.start_time: float = entry.get('start_time', 0.0)
        self.playlist: object | None = playlist
        self.uploader: tuple[str | None, str | None] = (entry.get('uploader'), entry.get('uploader_url'))
        self.upload_date: str | None = '/'.join(
            upload_date[x:y] for x, y in ((-2, None), (-4, -2), (-8, -4))
        ) if (upload_date := entry.get('upload_date')) else upload_date
        self.view_count: int | None = entry.get('view_count')
        self.thumbnail: str | None = thumbnails[-1]['url'] if (thumbnails := entry.get('thumbnails')) else thumbnails
        self.direct: str | None = entry.get('url')
        self.url: str = entry.get('webpage_url', self.direct)
        self.spotify: bool = entry.get('spotify', False)
        self.playlist_type: Pattern | None = entry.get('playlist_type')
        self.requested_by: Member = requested_by
        self.voting_: tuple[
            dict[
                tuple[str, tuple[str | int | TextChannel | VoiceChannel | Role, ...]],
                list[set[Member], Ctx, Message | ApplicationCommandInteraction]
            ],
            Thread
        ] | None = None

    def embed(self, requested_by: bool = True) -> Callable[[Embed], Embed]:
        def embed__(embed_: Embed) -> Embed:
            embed_.add_field('Title', esc(self.title, self.url))
            embed_.add_field('Duration', self.duration)
            if self.start_time: embed_.add_field('Start time', to_hms(self.start_time))
            if self.playlist: embed_.add_field('Playlist', esc(self.playlist.name, *((self.playlist.url,) if not self.playlist.search else ())))
            if self.uploader[0]: embed_.add_field('Uploader', esc(self.uploader[0], self.uploader[1]))
            if self.upload_date: embed_.add_field('Upload date', self.upload_date)
            if self.view_count: embed_.add_field('View count', f'{self.view_count:,}'.replace(',', ' '))
            if (direct := esc('direct', self.direct, retfalse = True)) if self.direct else False: embed_.add_field('Download', direct)
            if self.thumbnail: embed_.set_image(self.thumbnail)
            if requested_by: embed_.add_field('Requested by', f'{esc(self.requested_by.name)}#{self.requested_by.discriminator}')

            return embed_

        return embed__

    def voting(self, ctx: Ctx) -> int: # returns a number of remaining votes required to invoke the command
        # voting_[0] - votings
        # voting_[1] - checker thread
        # -----------------------------------------
        # voting_[0][invoke][0] - voters
        # voting[0][invoke][1] - context of invoker
        if not self.voting_:
            self.voting_ = (
                {},
                Thread(target = self.voting__, args = (ctx,), daemon = True)
            )


        for x, y in (*self.voting_[0].items(),):
            if x[0] == ctx.invoke[0] and ctx.author in y[0]: y[0].remove(ctx.author); break

        if ctx.invoke not in (voting := self.voting_[0]):
            voting[ctx.invoke] = [{ctx.author}, ctx, ctx.ctx]

            ctx.enforce_dj = True


            if not self.voting_[1].is_alive(): self.voting_[1].start()
        else:
            voting[ctx.invoke][2] = ctx.ctx
            voting[ctx.invoke][0].add(ctx.author)



        return len({x for x in ctx.voice_client.channel.members if not x.bot}) // 2 + 1 - len(self.voting_[0][ctx.invoke][0])
    def voting__(self, ctx: Ctx):
        while self in sm.assign[ctx].queue:
            if not self.voting_[0]: self.voting_ = None; return

            for x, y in (*self.voting_[0].items(),):
                for z in {*y[0]}:
                    if z not in ctx.voice_client.channel.members: y[0].remove(z)

                if not y[0]: del self.voting_[0][x]; continue

                if len({x for x in ctx.voice_client.channel.members if not x.bot}) // 2 + 1 - len(y[0]) <= 0:
                    y[1].ctx, y[1].response[0] = y[2], False

                    sm.client.loop.create_task(
                        sm.invoke_command(y[1])
                    )

                    del self.voting_[0][x]


            tsleep(0.333)
        else:
            self.voting_ = None

class Playlist:
    def __init__(self, playlist: dict, requested_by: Member):
        self.name: str = playlist['title']
        self.uploader: tuple[str | None, str | None] = (playlist.get('uploader'), playlist.get('uploader_url'))
        self.upload_date: str | None = '/'.join(
            upload_date[x:y] for x, y in ((-2, None), (-4, -2), (-8, -4))
        ) if (upload_date := playlist.get('upload_date')) else upload_date
        self.view_count: int | None = playlist.get('view_count')
        self.thumbnail: str | None = thumbnails[-1]['url'] if (thumbnails := playlist.get('thumbnails')) else thumbnails
        self.entries: list[Entry] = [
            (
                x.__setitem__('webpage_url', x.pop('url')),

                Entry(x, requested_by, self)
            )[1] for x in playlist['entries']
        ]
        self.url: str | None = playlist.get('webpage_url')
        self.search: bool = playlist['extractor'].endswith(':search')
        self.requested_by: Member = requested_by

    def embed(self, requested_by: bool = True) -> Callable[[Embed], Embed]:
        def embed__(embed_: Embed) -> Embed:
            embed_.add_field('Title', esc(self.name, *((self.url,) if not self.search else ())))
            if self.uploader[0]: embed_.add_field('Uploader', esc(self.uploader[0], self.uploader[1]))
            if self.upload_date: embed_.add_field('Last modification date', self.upload_date)
            if self.view_count: embed_.add_field('View count', f'{self.view_count:,}'.replace(',', ' '))
            embed_.add_field('Number of entries', len(self.entries))
            if self.thumbnail: embed_.set_image(self.thumbnail)
            if requested_by: embed_.add_field('Requested by', f'{esc(self.requested_by.name)}#{self.requested_by.discriminator}')

            return embed_

        return embed__

SPOTIFY: Pattern = compile(r'https?://open\.spotify\.com/(playlist|album|artist|track|episode|show)/(.+?(?=\?|$|/))')
class Quiet:
    @staticmethod
    def error(msg: str): ...
    @staticmethod
    def warning(msg: str): ...
    @staticmethod
    def debug(msg: str): ...
def resolve_(source: str, process: bool, ret: list[dict | Exception]):
    try:
        if not (uri := [*getattr(SPOTIFY.match(source), 'groups', lambda: ())()]):
            ret_ = YoutubeDL({
                'extract_flat': 'in_playlist' if not process else False,
                'format': 'bestaudio/best',
                'default_search': 'ytsearch',
                'noplaylist': True,
                'simulate': True,
                'nocheckcertificate': True,
                'source_address': '0.0.0.0',
                'logger': Quiet
            }).extract_info(source)

            if 'entries' in ret_:
                if ret_['extractor'].endswith(':search'):
                    ret_['title'] += ' (searching results)'

                    if len(ret_['entries']) == 1:
                        if not process:
                            resolve_(ret_['entries'][0]['url'], True, ret); return
                        else:
                            ret_ = ret_['entries'][0]
                    elif not ret_['entries']:
                        raise Exception('Nothing found :′(')
                elif not ret_['entries']:
                    raise Exception('Requested playlist is empty or provided URL is invalid (ಠ_ಠ)')
                else:
                    for x in ret_['entries']:
                        if 'entries' in x: ret_ = x; break
            if 'entries' in ret_ and process:
                raise Exception('Queue entry is a playlist (ಠ_ಠ)')

            if not ('duration' in ret_ or 'entries' in ret_):
                if ret_['format_id'] not in {'x-scpls', 'scpls', '9', '99'}:
                    ret_['duration'] = float(duration) if (duration := loads(
                        run([
                            'ffprobe',
                            '-print_format', 'json',
                            '-show_format', '-show_streams',
                            '-v', 'quiet',
                            ret_['url']
                        ], stdout = PIPE, universal_newlines = True, stderr = DEVNULL, stdin = DEVNULL).stdout
                    ).get('format', {}).get('duration')) else 'Stream or unplayable'
                else:
                    ret_['duration'], ret_['playlist_type'] = 'Stream', PLS if ret_['format_id'] in {'x-scpls', 'scpls'} else M3U
        else:
            ret_ = getattr(
                sm.spotify,
                uri[0] if not uri[0] == 'artist' else 'artist_albums'
            )(
                uri[1],
                **({'market': 'US'} if uri[0] in {'episode', 'show'} else {})
            )

            if ret_.get('album_type') == 'single': ret_, uri[0] = ret_['tracks']['items'][0], 'track'

            if uri[0] not in {'track', 'episode'}:
                match uri[0]:
                    case 'playlist':
                        ret_['tracks'] = (
                            x['track'] for x in (
                                *ret_['tracks']['items'],
                                *(
                                    x for y in (
                                        sm.spotify.playlist_tracks(uri[1], offset = 100 * z)['items'] for z in range(1, int(ret_['tracks']['total'] / 100) + 1)
                                    ) for x in y
                                )
                            )
                        )
                    case 'album':
                        ret_['tracks'], ret_['owner'] = ret_['tracks']['items'], (
                            owner := ret_.pop('artists')[0],
                            owner.__setitem__('display_name', owner.pop('name'))
                        )[0]
                    case 'artist':
                        ret_['tracks'], ret_['owner'], ret_['name'], ret_['external_urls'], ret_['images'] = (
                            x for y in (
                                sm.spotify.album_tracks(x['id'])['items'] for x in ret_.pop('items') if x['album_group'] != 'appears_on'
                            ) for x in y
                        ), *(
                            artist := sm.spotify.artist(uri[1]),
                            artist['name'],
                            artist['external_urls'],
                            artist['images'],

                            artist.__setitem__('display_name', artist.pop('name'))
                        )[:4]
                    case 'show':
                        ret_['tracks'] = (
                            *(episodes := ret_.pop('episodes'))['items'],
                            *(
                                x for y in (
                                    sm.spotify.show_episodes(uri[1], offset = 50 * z, market = 'US')['items'] for z in range(1, int(episodes['total'] / 50) + 1)
                                ) for x in y
                            )
                        )

                ret_ = {
                    'title': ret_['name'],
                    **(
                        uploader := {
                            'uploader': ret_['owner']['display_name'],
                            'uploader_url': ret_['owner']['external_urls']['spotify']
                        } if (notshow := uri[0] != 'show') else {
                            'uploader': ret_['publisher']
                        }
                    ),
                    **(
                        modified_date := {
                            'modified_date': ret_['release_date'].replace('-', '')
                        } if (album := uri[0] == 'album') else {}
                    ),
                    'thumbnails': ret_['images'],
                    'entries': [
                        {
                            'title': x['name'],
                            'duration': x['duration_ms'] / 1000,
                            **(
                                  {
                                    'uploader': x['artists'][0]['name'],
                                    'uploader_url': x['artists'][0]['external_urls']['spotify']
                                  } if notshow else uploader
                            ),
                            **(
                                {
                                    'modified_date': (x['album'] if uri[0] == 'playlist' else x)['release_date'].replace('-', '')
                                } if not album else modified_date
                            ),
                            'url': x['external_urls']['spotify'],
                            'spotify': True
                        } for x in ret_['tracks']
                    ],
                    'webpage_url': ret_['external_urls']['spotify']
                }
            else:
                ret_ = {
                    'title': ret_['name'],
                    'duration': ret_['duration_ms'] / 1000,
                    **(
                        {
                            'uploader': ret_['artists'][0]['name'],
                            'uploader_url': ret_['artists'][0]['external_urls']['spotify'],
                            'upload_date': ret_['album']['release_date'].replace('-', ''),
                            'thumbnails': ret_['album']['images']
                        } if uri[0] == 'track' else {
                            'uploader': ret_['show']['publisher'],
                            'upload_date': ret_['release_date'].replace('-', ''),
                            'thumbnails': ret_['images']
                        }
                    ),
                    'webpage_url': ret_['external_urls']['spotify'],
                    'spotify': True
                }

            ret_['extractor'] = f'spotify:{uri[0]}'
    except Exception as ex:
        ret_ = ex

    ret.append(ret_)
async def resolve(source: str, requested_by: Member, playlist: Playlist | None = None, process: bool = False, timeout: float = 5) -> Entry | Playlist:
    ret = []
    t, tt = (
        t_ := Thread(target = resolve_, args = (source, process, ret), daemon = True),
        t_.start()
    )[0], perf_counter()

    while t.is_alive():
        if perf_counter() - tt >= timeout:
            pythonapi.PyThreadState_SetAsyncExc(c_ulong(t.ident), py_object(Exception))


            raise Exception(f'Timed out :/ (requested operation took > {timeout} secs)')


        await sleep(0.333)
    else:
        ret = ret[0]

        if not isinstance(ret, Exception):
            return (Entry if (entries := 'entries' not in ret) else Playlist)(ret, requested_by, *((playlist,) if entries else ()))
        else:
            raise ret