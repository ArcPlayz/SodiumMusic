import builtins as sm

from disnake import Client, Intents, SlashCommand, ApplicationCommandInteraction, Message, Guild

from utils import Ctx
from re import match, compile, Pattern

from ast import literal_eval
from pickle import dump, load

from threading import Thread
from time import sleep



sm.client = Client(intents = Intents.all())

sm.config = literal_eval(open('config.sm', 'r').read())

class Settings(dict[int, dict]):
    def __init__(self):
        super().__init__(load(open('settings.sm', 'rb')))

        self.st = Thread(target = self.sync, daemon = True)

    def __getitem__(self, g: Guild) -> dict:
        if g.id not in self.keys(): self[g.id] = {
            'prefix': ';',
            'effects': set(),
            'volume': 100,
            'dj_role': g.id,
            'voting': False
        }


        return super().__getitem__(g.id)


    def sync(self):
        while True:
            for x in {*self}:
                if x not in {g.id for g in sm.client.guilds}:
                    del self[x]

                    for y in {*sm.assign}:
                        if y.id == x: del sm.assign[y]; break


            dump({**self}, open('settings.sm', 'wb'))



            sleep(0.333)
sm.settings = Settings()


MESSAGE: Pattern = compile(r'[ \n]')
@sm.client.event
async def on_message(msg: Message):
    if (prefix := getattr(
        match(f'^((<@{sm.client.user.id}>[ {chr(92)}n]*)|{sm.settings[msg.guild]["prefix"]})', msg.content),
        'group',
        lambda: ()
    )()) and not msg.author.bot:
        await sm.invoke_command(
            Ctx(
                msg,
                (
                    (invoke := MESSAGE.split(msg.content[len(prefix):]))[0],
                    tuple(invoke[1:])
                )
            )
        )

@sm.client.event
async def on_application_command(inter: ApplicationCommandInteraction):
    await sm.invoke_command(
        Ctx(
            inter,
            (
                inter.data.name,
                tuple(x.value for x in inter.data.options)
            )
        )
    )

@sm.client.event
async def on_ready():
    import main

    await sm.client.bulk_overwrite_global_commands([
        SlashCommand(
            x[0],
            f'{y[2]} {y[3]}',
            [z[0].option(z[1]) for z in y[1]],
        ) for x, y in sm.commands
    ])


    sm.settings.st.start()


    @sm.client.event
    async def on_ready(): ...

    print(
f'''Connected as {sm.client.user.name}#{sm.client.user.discriminator}.

Invite URL:
https://discord.com/oauth2/authorize?client_id={sm.client.user.id}&permissions=8&scope=bot'''
    )
sm.client.run(sm.config['token'])