#!/usr/bin/env python3

''' TCP Proxy

This module creates a TCP proxy and handles connections between clients and a
remote server. Multiple clients can be handled simultaneously. Each client is
assigned a separate thread. The proxy does not assume anything about the nature
of the traffic between a client and the remote server. To achieve this goal,
two non-blocking sockets are used in each thread; one for connecting to the client
and one for connecting to the remote server. Whenever there is incoming data on a
socket, 'select' function returns that socket. If there is incoming data from the
client, that data is immediately forwarded to the remote server. With the same
logic, if there is incoming data from the server, data is forwarded to the client.

Usage:
    Run the script and wait for incoming clients:
    $ ./proxy.py [-h] local_ip local_port remote_ip remote_port
'''

import socket
import select
import sys
import queue
import threading
import argparse

MAX_CONNECTIONS = 5     # max number of simultaneously supported clients
BUFFER_SIZE = 2048      # buffer size for socket receive operations
SELECT_TIMEOUT = 3      # timeout for 'select' function

class TCP_proxy():
    def __init__(self, local_ip, local_port, remote_ip, remote_port):
        ''' Initiates the class variables

        Parameters:
            local_ip (str): Local IP for the proxy to bind to
            local_port (int):  Local port number for the proxy to bind to
            remote_ip (str): IP of the remote server
            remote_port (int): Port number of the remote server
        '''
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.main_loop()

    def main_loop(self):
        ''' Continuously listens for incoming clients. When a connection is
        established, passes the connection to the client_handler thread.
        '''
        main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        main_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        main_socket.bind((self.local_ip, self.local_port))
        main_socket.listen(MAX_CONNECTIONS)
        while True:
            client_socket, client_addr = main_socket.accept()
            print("Client connected: {}:{}\n".format(client_addr[0], client_addr[1]))
            client_args = (client_socket, client_addr)
            client_thread = threading.Thread(target=self.client_handler, args=client_args)
            client_thread.start()

    def client_handler(self, client_socket, client_addr):
        ''' Handles the traffic for each client. Keeps two non-blocking sockets:
        client_socket for communicating with the client and remote_socket for
        communicating with the remote server. When client_socket receives data,
        the handler immediately forwards it to the remote_server and vice versa.
        '''
        try:
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.connect((self.remote_ip, self.remote_port))
        except socket.error:
            print('Cannot connect to remote server!\n')
            client_socket.close()
            return

        remote_socket.setblocking(0)
        client_socket.setblocking(0)

        inputs = [client_socket, remote_socket]
        outputs = []
        message_queues = {client_socket:queue.Queue(), remote_socket:queue.Queue()}

        while inputs:
            # wait for socket activity or a timeout
            readable, writable, exceptional = select.select(inputs, outputs, inputs, SELECT_TIMEOUT)

            # in the event of a timeout, tear down the connection
            if not (readable or writable):
                print('TIMEOUT!')
                remote_socket.close()
                if client_socket in inputs:
                    print('Client disconnected: {}:{}\n'.format(client_addr[0], client_addr[1]))
                    client_socket.close()
                break

            # traverse over readable sockets
            for s in readable:
                if s is client_socket:      # if client socket received data
                    try:
                        data = s.recv(BUFFER_SIZE)
                    except socket.error:
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]
                    else:
                        if data:
                            if remote_socket in inputs:
                                # forward the data to remote_socket's queue
                                message_queues[remote_socket].put(data)
                                if remote_socket not in outputs:
                                    outputs.append(remote_socket)
                        else:
                            # empty receive means connection is over
                            print('Client disconnected: {}:{}\n'.format(client_addr[0], client_addr[1]))
                            if s in outputs:
                                outputs.remove(s)
                            inputs.remove(s)
                            s.close()
                            del message_queues[s]

                elif s is remote_socket:        # if remote server received data
                    try:
                        data = s.recv(BUFFER_SIZE)
                    except socket.error:
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]
                    else:
                        if data:
                            if client_socket in inputs:
                                # forward the data to client_socket's queue
                                message_queues[client_socket].put(data)
                                if client_socket not in outputs:
                                    outputs.append(client_socket)
                        else:
                            # empty receive means connection is over
                            if s in outputs:
                                outputs.remove(s)
                            inputs.remove(s)
                            s.close()
                            del message_queues[s]

            # traverse over writable sockets
            for s in writable:
                try:
                    message = message_queues[s].get_nowait()
                except:
                    continue
                else:
                    # send data if this socket has data to send in it's queue
                    try:
                        s.sendall(message)
                    except socket.error:
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]
                        if s is client_socket:
                            print('Client disconnected: {}:{}\n'.format(client_addr[0], client_addr[1]))
                    else:
                        # print data exchange to the console
                        if s is client_socket:
                            print('[{}:{}] <------- [SERVER]\t{} bytes\n0x{}\n'.format(client_addr[0], client_addr[1], len(message), message.hex()))
                        else:
                            print('[{}:{}] -------> [SERVER]\t{} bytes\n0x{}\n'.format(client_addr[0], client_addr[1], len(message), message.hex()))

            # traverse over erroneous sockets and close them
            for s in exceptional:
                inputs.remove(s)
                if s in outputs:
                    outputs.remove(s)
                s.close()
                del message_queues[s]

            # tear down connection if one party has disconnected
            if len(inputs) < 2:
                if client_socket in inputs:
                    print('Client disconnected: {}:{}\n'.format(client_addr[0], client_addr[1]))
                    client_socket.close()
                break

# Parse command line arguments and start the TCP Proxy
parser = argparse.ArgumentParser(description='TCP Proxy')
parser.add_argument("local_ip", help="ip of the proxy")
parser.add_argument("local_port", help="port of the proxy", type=int)
parser.add_argument("remote_ip", help="ip of the remote server")
parser.add_argument("remote_port", help="port of the remote server", type=int)
args = parser.parse_args()
proxy = TCP_proxy(args.local_ip,args.local_port,args.remote_ip,args.remote_port)
