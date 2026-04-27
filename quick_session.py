import asyncio, sys
from pyrogram import Client

async def gen():
    app = Client('quick_sess', api_id=27798659, api_hash='26100c77cee02e5e34b2bbee58440f86', in_memory=True)
    await app.connect()
    code_info = await app.send_code('+17192019024')
    print(f'HASH:{code_info.phone_code_hash}', flush=True)
    print('WAITING_FOR_CODE', flush=True)
    # Read code from stdin
    otp = input()
    try:
        await app.sign_in('+17192019024', code_info.phone_code_hash, otp.strip())
        session = await app.export_session_string()
        print(f'SESSION:{session}', flush=True)
    except Exception as e:
        print(f'ERROR:{e}', flush=True)
    await app.disconnect()

asyncio.run(gen())
