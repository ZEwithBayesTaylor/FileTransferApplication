import sys
import socket
import threading
from threading import Thread
import time
from typing import Dict, List, Tuple, Union
import signal
import ipaddress
import argparse
import os

# this is client side

'''
UDP client process:
create socket(socket()) -> bind to port(bind()) -> send data(sendto()) -> receive reply(recvfrom()) -> client exit(close())
'''

class FileAppClient:
    def __init__(self, name, server_ip, server_port, client_udp_port, client_tcp_port):
        self.name = name
        self.server_ip = server_ip
        self.server_port = server_port
        self.client_udp_port = client_udp_port
        self.client_tcp_port = client_tcp_port

        # create UDP and TCP socket for client
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # bind socket(ip) to a port
        self.udp_socket.bind(('', client_udp_port))

        # create client local table
        self.client_table = {}

        self.dir = None

    def register(self):
        # create registration msg
        message = f"REGISTER {self.name} {socket.gethostbyname(socket.gethostname())} {self.client_udp_port} {self.client_tcp_port}"

        # encode the msg and send to server
        self.udp_socket.sendto(message.encode(), (self.server_ip, self.server_port))

        # deal with server response
        data, addr = self.udp_socket.recvfrom(1024)
        response = data.decode().split(" ", 1)

        if response[0] == "WELCOME":
            print(">>> [Welcome, You are registered.]")
            self.update_client_table(response[1])
        else:
            print(">>> [Error: Registration failed.]")
            sys.exit(1)

    def print_client_table(self):
        print("\nClient Table:")
        for name, info in self.client_table.items():
            print(f"{name}: {info}")
        print("\n")

    def update_client_table(self, table_data):
        # Deserialize the table_data and update self.client_table
        # After updating, send an ACK message to the server
        self.client_table = self.deserialize_table(table_data)
        self.udp_socket.sendto("ACK".encode(), (self.server_ip, self.server_port))

    def deserialize_table(self, table_data: str) -> Dict[str, Dict[str, Union[str, int, List[str], bool]]]:
        table = {}
        for row in table_data.strip().split('\n'):
            name, ip, udp_port, tcp_port, online, *files = row.split(' ')
            table[name] = {
                "ip": ip,
                "udp_port": int(udp_port),
                "tcp_port": int(tcp_port),
                "files": files,
                "online": bool(int(online))
            }
        return table

    def sigint_handler(self, signum, frame):
        self.handle_disconnect(silent=True)

    def handle_disconnect(self, silent: bool = False):
        if not silent:
            message = f"DISCONNECT {self.name}"
            self.udp_socket.sendto(message.encode(), (self.server_ip, self.server_port))

        self.udp_socket.close()
        self.tcp_socket.close()
        sys.exit(0)

    def handle_input(self):
        self.setdir(os.getcwd())

        while True:
            try:
                command = input("Enter command (table/help/disconnect/request/list/setdir/offer): ").strip().lower()
                cmd_parts = command.split()

                if command == "table":
                    self.print_client_table()
                elif cmd_parts[0] == "setdir":
                    if len(cmd_parts) == 2:
                        self.setdir(cmd_parts[1])
                    else:
                        print("Invalid setdir command. Usage: setdir <directory>")
                elif cmd_parts[0] == "offer":
                    if len(cmd_parts) > 1:
                        self.offer(*cmd_parts[1:])
                    else:
                        print("Invalid offer command. Usage: offer <filename1> <filename2> ...")
                elif cmd_parts[0] == "list":
                    self.list_files()
                elif command == "help":
                    print("Available commands:")
                    print("  table      - print the client table")
                    print("  help       - show this help message")
                    print("  disconnect - disconnect and notify the server")
                    print("  request <filename> <client> - request a file from another client")
                elif command == "disconnect":
                    self.handle_disconnect(silent=False)
                    break
                elif cmd_parts[0] == "request":
                    if len(cmd_parts) == 3:
                        filename, target_client = cmd_parts[1], cmd_parts[2]
                        self.request_file(filename, target_client)
                    else:
                        print("Invalid request command. Usage: request <filename> <client>")
                # Add other commands like list, setdir, and offer here
                else:
                    print("Unknown command. Type 'help' for available commands.")
            except KeyboardInterrupt:
                self.handle_disconnect(silent=False)
                break
    def list_files(self):
        file_list = []
        for name, info in self.client_table.items():
            for file in info['files']:
                file_list.append((file, name))

        if not file_list:
            print(">>> [No files available for download at the moment.]")
            return

        print("\nFile Offerings:")
        file_list.sort(key=lambda x: (x[0], x[1]))
        for file, name in file_list:
            print(f"{file} - offered by {name}")
        print("\n")

    def request_file(self, filename: str, target_client: str):
        target_client = target_client.lower()  # Convert the provided client name to lowercase

        # Search for the target client in the client_table using a case-insensitive comparison
        matching_client = None
        for name in self.client_table:
            if name.lower() == target_client:
                matching_client = name
                break

        if not matching_client:
            print(f">>> Invalid Request: Client '{target_client}' does not exist in the client table.")
            return

        if filename not in self.client_table[matching_client]['files']:
            print(f">>> Invalid Request: File '{filename}' is not available from client '{matching_client}'.")
            return

        file_owner = self.client_table[matching_client]
        ip = file_owner["ip"]
        tcp_port = file_owner["tcp_port"]

        # Create a new TCP socket for each request
        request_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Establish a TCP connection with the file owner
            request_tcp_socket.connect((ip, tcp_port))
            print("<TCP connection established with file owner>")

            # Send a request for the file
            request_tcp_socket.sendall(f"REQUEST {filename}".encode())
            print("Sent file request")

            # Receive the file size
            file_size_str = request_tcp_socket.recv(1024).decode()
            print(f"Received file size string: {file_size_str}")
            file_size = int(file_size_str)
            print(f"Received file size: {file_size}")
            # Receive the file
            with open(os.path.join(self.dir, filename), 'wb') as file:
                received_size = 0
                while received_size < file_size:
                    data = request_tcp_socket.recv(1024)
                    received_size += len(data)
                    file.write(data)

            print("<File transfer complete>")

        except Exception as e:
            print(f">>> Error requesting file: {str(e)}")
        finally:
            request_tcp_socket.close()

    def start_tcp_server(self, port):
        tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_server_socket.bind(('', port))
        tcp_server_socket.listen(5)

        print(f"TCP server started at :{port}")

        while True:
            conn, addr = tcp_server_socket.accept()
            print(f"<TCP Connection established with {addr[0]}:{addr[1]}>")

            request_handler = threading.Thread(target=self.handle_incoming_request, args=(conn, addr))

            request_handler.start()

    def handle_incoming_request(self, conn, addr):
        received_message = conn.recv(1024).decode()
        print(f"Received request: {received_message}")

        # Extract the filename from the received message
        command, filename = received_message.split(" ", 1)

        file_path = os.path.join(self.dir, filename)
        print(f"<Sending file '{filename}' to {addr[0]}:{addr[1]}>")

        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)
            print(f"File size: {file_size}")

            conn.send(str(file_size).encode())
            print(f"Sent file size: {file_size}")

            with open(file_path, "rb") as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    conn.sendall(data)

            print(f"<File '{filename}' sent>")
        else:
            print(f"<Error: File '{filename}' not found>")

        conn.close()
        print(f"<TCP Connection closed with {addr[0]}:{addr[1]}>")

    def run(self):
        while True:
            try:
                # Check for incoming table updates from the server
                data, addr = self.udp_socket.recvfrom(1024)
                message = data.decode().split(" ", 1)
                if message[0] == "UPDATE":
                    old_table = self.client_table.copy()
                    self.update_client_table(message[1])
                    if old_table != self.client_table:
                        print("\n>>> [Client table updated.]", end="", flush=True)
            except OSError:
                break

    def setdir(self, dir: str):
        if os.path.isdir(dir):
            self.dir = dir
            print(f">>> [Successfully set {dir} as the directory for searching offered files.]")
        else:
            print(f">>> [setdir failed: {dir} does not exist.]")

    def offer(self, *filenames: str, retry: int = 2):
        if self.dir is None:
            print(">>> [Error: setdir must be called before offering files.]")
            return

        filenames = [filename for filename in filenames if os.path.isfile(os.path.join(self.dir, filename))]
        if not filenames:
            print(">>> [No valid files to offer.]")
            return

        # Update client's own table with the offered files
        for filename in filenames:
            if filename not in self.client_table[self.name]["files"]:
                self.client_table[self.name]["files"].append(filename)

        message = f"OFFER {self.name} {' '.join(filenames)}"
        self.udp_socket.sendto(message.encode(), (self.server_ip, self.server_port))

        # Wait for ack from the server
        attempts = 0
        while attempts <= retry:
            start_time = time.time()
            while time.time() - start_time < 0.5:
                data, addr = self.udp_socket.recvfrom(1024)
                if data.decode() == "ACK":
                    print(">>> [Offer Message received by Server.]")
                    return
            attempts += 1

        print(">>> [No ACK from Server, please try again later.]")

    def deregister(self):
        self.tcp_socket.close()
        self.udp_socket.sendto(f"DEREG {self.name}".encode(), (self.server_ip, self.server_port))
        attempts = 0
        while attempts < 3:
            self.udp_socket.settimeout(0.5)
            try:
                response, _ = self.udp_socket.recvfrom(1024)
                if response.decode() == "ACK":
                    print(">>> [You are Offline. Bye.]")
                    return
            except socket.timeout:
                attempts += 1
                self.udp_socket.sendto(f"DEREG {self.name}".encode(), (self.server_ip, self.server_port))

        print(">>> [Server not responding]")
        print(">>> [Exiting]")
        sys.exit()



# -----------------------
# this is server side

'''
UDP server process:
create socket(socket()) -> bind to port(bind()) -> receive data(recvfrom()) -> send reply(sendto()) -> server exit(close())
'''

class FileAppServer:
    def __init__(self, port):
        self.port = port
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('', port))

        # key: client names, values: client info (ip, udp_port, tcp_port...)
        self.client_table = {}

    # listening for incoming UDP msg
    def listen_udp(self):
        while True:
            data, addr = self.udp_socket.recvfrom(1024)
            message = data.decode().split(" ")
            if message[0] == "REGISTER":
                self.handle_registration(message[1:], addr)
                self.print_client_table()
            elif message[0] == "DEREG":  # Change 'DISCONNECT' to 'DEREG' to match client's message
                self.handle_deregistration(message[1:], addr)
                self.print_client_table()
            elif message[0] == "ACK":
                pass  # Do nothing, just acknowledge the receipt of the update
            elif message[0] == "OFFER":
                self.handle_offer(message[1:])
                self.print_client_table()

    def handle_deregistration(self, message, addr):
        nickname = message[0]

        if nickname in self.client_table:
            self.client_table[nickname]["online"] = False
            self.udp_socket.sendto("ACK".encode(), addr)

            # Broadcast the updated client_table to all online clients
            self.broadcast_table()
        else:
            print(f">>> Invalid de-registration request: Client '{nickname}' not found.")

    def handle_offer(self, message):
        client_name = message[0]
        offered_files = message[1:]

        if client_name in self.client_table:
            client = self.client_table[client_name]
            for filename in offered_files:
                if filename not in client["files"]:
                    client["files"].append(filename)
            self.broadcast_table()
            self.udp_socket.sendto("ACK".encode(), (client["ip"], client["udp_port"]))

    def handle_registration(self, message, addr):
        name, ip, udp_port, tcp_port = message
        if name in self.client_table and self.client_table[name]["online"]:
            self.udp_socket.sendto("ERROR".encode(), addr)
        else:
            self.client_table[name] = {
                "ip": ip,
                "udp_port": int(udp_port),
                "tcp_port": int(tcp_port),
                "files": self.client_table.get(name, {}).get("files", []),
                "online": True
            }
            table_data = self.serialize_table()
            self.udp_socket.sendto(f"WELCOME {table_data}".encode(), addr)
            self.broadcast_table()

    def serialize_table(self) -> str:
        rows = []
        for name, info in self.client_table.items():
            row = f"{name} {info['ip']} {info['udp_port']} {info['tcp_port']} {int(info['online'])} {' '.join(info['files'])}"
            rows.append(row)
        return '\n'.join(rows)

    def handle_disconnect(self, message):
        name = message[0]
        if name in self.client_table:
            self.client_table[name]["online"] = False
            self.broadcast_table()

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ipaddress.AddressValueError:
            return False

    @staticmethod
    def is_valid_port(port: int) -> bool:
        return 1024 <= port <= 65535

    def print_client_table(self):
        print("\nClient Table:")
        for name, info in self.client_table.items():
            print(f"{name}: {info}")
        print("\n")

    def broadcast_table(self):
        table_data = self.serialize_table()
        for name, info in self.client_table.items():
            if info['online']:
                addr = (info['ip'], info['udp_port'])
                self.udp_socket.sendto(f"UPDATE {table_data}".encode(), addr)
            else:
                self.udp_socket.sendto(f"DISCONNECTED {name}".encode(), (info['ip'], info['udp_port']))

    def run(self):
        print(f"Server started on port {self.port}. Waiting for incoming messages...")
        self.listen_udp()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="File Transfer App")
    parser.add_argument("-s", "--server", type=int, help="Start a server at the specified port")
    parser.add_argument("-c", "--client", nargs=5, help="Start a client with: name, server IP, server port, udp port, tcp port")

    args = parser.parse_args()

    if args.server:
        server = FileAppServer(args.server)
        server.run()
    elif args.client:
        name, server_ip, server_port, udp_port, tcp_port = args.client
        client = FileAppClient(name, server_ip, int(server_port), int(udp_port), int(tcp_port))
        client.register()

        # Start the TCP server for handling file requests in a separate thread
        tcp_server_thread = threading.Thread(target=client.start_tcp_server, args=(int(tcp_port),), daemon=True)
        tcp_server_thread.start()

        # Start a separate thread for client.run() to listen for updates from the server
        update_listener_thread = threading.Thread(target=client.run, daemon=True)
        update_listener_thread.start()

        # client.listen_for_disconnect()

        while True:
            try:
                command = input("Enter command (setdir/offer/table/help/list/request/dereg/disconnect): ").strip().lower()
                if command.startswith("setdir"):
                    command_split = command.split(" ", 1)
                    if len(command_split) == 2:
                        _, dir = command_split
                        client.setdir(dir)
                    else:
                        print(">>> [Error: setdir command requires a directory argument. Usage: setdir <directory>]")

                elif command.startswith("offer"):
                    _, *filenames = command.split(" ")
                    client.offer(*filenames)
                elif command == "table":
                    client.print_client_table()
                elif command == "list":
                    client.list_files()
                elif command.startswith("request"):
                    command_split = command.split(" ")
                    if len(command_split) == 3:
                        _, filename, target_client = command_split
                        client.request_file(filename, target_client)
                    else:
                        print(
                            ">>> [Error: request command requires a filename and client name. Usage: request <filename> <client>]")
                elif command == "dereg":
                    client.deregister()




                elif command == "help":
                    print("Available commands:")
                    print("  setdir      - set the directory for searching offered files")
                    print("  offer       - offer one or more files to other clients")
                    print("  table       - print the client table")
                    print("  help        - show this help message")
                    print("  disconnect  - disconnect and notify the server")
                elif command == "disconnect":
                    client.handle_disconnect(silent=False)
                    break

                else:
                    print("Unknown command. Type 'help' for available commands.")
            except KeyboardInterrupt:
                client.handle_disconnect(silent=False)
                break

    else:
        print("Invalid usage. Use '-h' or '--help' for help.")