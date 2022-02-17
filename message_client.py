import asyncio
import json
import logging
from uuid import uuid4

log = logging.getLogger()

log.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%d.%m.%y %H:%M:%S",
)

terminal_handler = logging.StreamHandler()
terminal_handler.setFormatter(formatter)
log.addHandler(terminal_handler)


class MessageClient:
    def __init__(self, host="127.0.0.1"):
        self.host = host
        self.uid = str(uuid4())
        self._token = None

    # This may be reasonable, but it messed with tests for token-less connection,
    # thus commented it out.
    # def require_token(func):
    #     async def wrap(self, *args, **kwargs):
    #         if self._token is None:
    #             await self.get_token()
    #         return await func(self, *args, **kwargs)
    #     return wrap

    async def get_token(self):
        try:
            reader, writer = await asyncio.open_connection(self.host, 8000)
        except Exception as e:
            log.warning(f"Unable to establish server connection: {e}")
        else:
            try:
                writer.write(self.uid.encode())
                await writer.drain()

                answ = await reader.read(100)
                self._token = answ.decode()
            except Exception as e:
                log.warning(f"Unable to get token: {e}")
            finally:
                writer.close()
                await writer.wait_closed()

    # @require_token
    async def send_message(self, msg: str):
        error = None
        msg = str(msg)  # Just in case our user doesn't read typehints
        try:
            reader, writer = await asyncio.open_connection(self.host, 8001)
        except Exception as e:
            error = f"Unable to establish server connection: {e}"
        else:
            try:
                full_msg = json.dumps(
                    {"uid": self.uid, "token": self._token, "msg": str(msg)}
                )
                writer.write(full_msg.encode())
                await writer.drain()

                answ = await reader.read(1000)
                answ = answ.decode()
                if answ:
                    error = answ
                else:
                    log.info(f"Message '{msg}' has been delivered")
            except Exception as e:
                error = f"Unable to send message: {e}"
            finally:
                writer.close()
                await writer.wait_closed()

        if error is not None:
            log.warning(error)


if __name__ == "__main__":
    # These aren't the real tests, but examples of how the application would behave
    # with and without token
    client = MessageClient()
    # This should fail
    asyncio.run(client.send_message("hello, world"))
    # And now this should pass
    asyncio.run(client.get_token())
    asyncio.run(client.send_message("hello, world"))
    asyncio.run(client.send_message("asda"))

    # Testing multiple clients
    for x in range(10):
        c = MessageClient()
        asyncio.run(c.get_token())
        asyncio.run(c.send_message(str(uuid4())))
