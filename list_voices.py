import edge_tts
import asyncio

async def main():
    voices = await edge_tts.list_voices()
    for v in voices:
        if 'IN' in v['Locale'] or 'hi' in v['Locale'].lower():
            print(f'{v["ShortName"]} - {v["Locale"]} - {v["Gender"]} - {v["FriendlyName"]}')

asyncio.run(main())