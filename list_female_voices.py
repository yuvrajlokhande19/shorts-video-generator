import edge_tts
import asyncio

async def main():
    voices = await edge_tts.list_voices()
    for v in voices:
        if v['Gender'] == 'Female':
            print(f'{v["ShortName"]} - {v["Locale"]} - {v["Gender"]} - {v["FriendlyName"]}')

asyncio.run(main())