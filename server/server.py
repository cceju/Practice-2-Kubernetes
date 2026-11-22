import os
import socket
import sys
import logging
from concurrent.futures import ThreadPoolExecutor

# Allow `from common.protocol import ...` when running from server/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import procedures
from common.protocol import ProtocolError, recv_msg, send_msg
from rpc_server import  ErrorCode, RPCServer

HOST = "0.0.0.0"
PORT = 5000
MAX_WORKERS = 4
CLIENT_TIMEOUT = 30  # seconds a client may take to send its request

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rpc.server")


def build_service() -> RPCServer:
    rpc = RPCServer()

    rpc.register(procedures.add)
    rpc.register(procedures.multiply)
    rpc.register(procedures.power)
    rpc.register(procedures.slow_task)
    rpc.register(procedures.image_info)
    rpc.register(procedures.grayscale)
    rpc.register(procedures.resize)

    return rpc

def handle(rpc: RPCServer, connection: socket.socket, address: tuple) -> None:
    with connection:
        # A client that connects and never sends would block a worker forever.
        connection.settimeout(CLIENT_TIMEOUT)
        try:
            request = recv_msg(connection)
            if request is None:
                # Kubernetes TCP probes open and close the socket without
                # sending anything: not an error, so keep it out of the log.
                log.debug("%s empty connection", address)
                return

            log.info("%s -> %s", address, request.get("function"))
            response = rpc.dispatch(request)
        except ProtocolError as e:
            log.warning("%s: unreadable message: %s", address, e)
            response = {
                "status": "error",
                "error": ErrorCode.BAD_MESSAGE,
                "message": str(e)
            }
        except OSError as e:
            log.warning("%s: network failure: %s", address, e)
            return

        try:
            send_msg(connection, response)
        except OSError as e:
            log.warning("%s: could not reply: %s", address, e)

def main():
    rpc = build_service()

    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()

        log.info("Listening on %s:%s", HOST, PORT)
        log.info("Procedures %s", ", ".join(rpc.procedures()))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            try:
                while True:
                    connection, address = server.accept()
                    pool.submit(handle, rpc, connection, address)
            except KeyboardInterrupt:
                log.info("Shutting down")
    
if __name__ == "__main__":
    main()
