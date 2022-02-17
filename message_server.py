import asyncio
import logging
import json
from uuid import uuid4

LOG_PATH = "./server_log.txt"

log = logging.getLogger()

log.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%d.%m.%y %H:%M:%S",
)

terminal_handler = logging.StreamHandler()
terminal_handler.setFormatter(formatter)
log.addHandler(terminal_handler)
file_handler = logging.FileHandler(LOG_PATH)
file_handler.setFormatter(formatter)
log.addHandler(file_handler)


class MessageServer:
    def __init__(self, host="127.0.0.1"):
        self.host = host

        # Trying to make it compatible with both python 3.10+ and older versions
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        except NameError:
            self._loop = asyncio.get_event_loop()

        # Storage for ID/token pairs
        # Assuming that current task doesn't require these to expire
        self.known_clients = {}

    async def assign_token(self, reader, writer):
        client_uid = await reader.read(100)

        # There may be more secure token generation mechanisms
        token = str(uuid4())
        self.known_clients[str(client_uid.decode())] = token

        writer.write(token.encode())
        await writer.drain()

        writer.close()
        await writer.wait_closed()

    async def handle_message(self, reader, writer):
        try:
            # This limit may malform our message, rendering it unreadable if its
            # too long. However, the only alternative I've found was to use
            # readuntil() which expects newline separator at the end of message.
            # Which, in case message has been malformed on purpose, would listen
            # to it indefinitely - and that would be much worse.
            msg = await reader.read(10000)

            msg = json.loads(msg.decode())

            uid = msg.get("uid")
            token = msg.get("token")
            txt = msg.get("msg")

            error = None

            if uid and txt:
                if token and self.known_clients.get(str(uid)) == str(token):
                    log.info(
                        f"Client {uid} has sent the following message: '{str(txt)}'"
                    )
                else:
                    error = "Invalid token error"
            else:
                error = "Invalid message format"

            # This could return not just errors, but also a success status, to
            # inform client that message has been received. But that would
            # require a proper response handler, with something like status
            # codes for both success state and various error types.
            # For the current task, I've considered it to be an overkill.
            if error is not None:
                log.warning(f"Unable to process a message: {error}")
                writer.write(error.encode())
                await writer.drain()
        except Exception as e:
            log.warning(f"Unable to handle message: {e}")

        writer.close()
        await writer.wait_closed()

    def run(self):
        self._loop.create_task(asyncio.start_server(self.assign_token, port=8000))
        self._loop.create_task(asyncio.start_server(self.handle_message, port=8001))
        self._loop.run_forever()


if __name__ == "__main__":
    serv = MessageServer()
    serv.run()
