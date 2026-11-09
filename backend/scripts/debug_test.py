import asyncio
print("1", flush=True)
async def f():
    print("2", flush=True)
asyncio.run(f())
print("3", flush=True)
