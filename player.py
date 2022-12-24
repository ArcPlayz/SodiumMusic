import builtins as sm

from disnake import AudioSource, VoiceChannel

from subprocess import Popen, PIPE, DEVNULL

from audioop import mul

from re import MULTILINE, compile, Pattern
from urllib.request import urlopen

from math import prod



NL: Pattern = compile(r'(\r\n)|\r')


class Player(AudioSource):
    channel: VoiceChannel | None = None


    src: str | None = None
    start_time: int | None = None

    elapsed: int | None = None

    playlist: list[str] | None = None

    process: Popen | None = None



    def play(self, src: str, start_time: int, playlist: Pattern | None) -> AudioSource:
        self.src = src
        self.start_time = start_time

        self.elapsed = start_time

        self.playlist = playlist.findall(
            NL.sub('\n', urlopen(src).read().decode('UTF-8')),

            MULTILINE
        ) if playlist else playlist


        return self.play_()

    def mp(self) -> float: return prod(
        sm.config['effects'][x][1] for x in sm.settings[self.channel.guild]['effects'] if type(sm.config['effects'][x]) is tuple
    )
    def play_(self) -> AudioSource:
        self.process = Popen(
            (
                'ffmpeg',
                '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                '-i', self.src if not self.playlist else self.playlist[0],
                *(('-ss', f'{self.elapsed / self.mp()}s') if self.elapsed else ()),
                *(
                    (
                        '-af',

                        ', '.join(
                            (
                                sm.config['effects'][x] if not type(sm.config['effects'][x]) is tuple else sm.config['effects'][x][0]
                            ) for x in sm.settings[self.channel.guild]['effects']
                        )
                    ) if sm.settings[self.channel.guild]['effects'] else ()
                ),
                '-f', 's16le',
                '-ar', '48000',
                '-ac', '2',
                '-'
            ),
            stdout = PIPE, stderr = DEVNULL, stdin = DEVNULL
        )


        return self
    def read(self, retries: int = 0) -> bytes:
        if len(buf := self.process.stdout.read(3840)) < 3840:
            if not (self.playlist or sm.assign[self.channel].loop == 'entry'): return b''
            else:
                if retries == (
                    (
                        self.playlist.append(self.playlist.pop(0)),

                        len(self.playlist)
                    ) if self.playlist else (
                        setattr(self, 'elapsed', self.start_time),

                        5
                    )
                )[1]:
                    if sm.assign[self.channel].loop == 'entry': sm.assign[self.channel].loop = False
                    sm.assign[self.channel].queue.pop()


                    return b''


                self.play_()

                return self.read(retries + 1)


        if not self.playlist: self.elapsed += 0.020 * self.mp()

        return mul(buf, 2, sm.settings[self.channel.guild]['volume'] / 100)