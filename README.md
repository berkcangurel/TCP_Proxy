# TCP Proxy

This module creates a TCP proxy and handles connections between clients and a
remote server. Multiple clients can be handled simultaneously. Each client is
assigned a separate thread. The proxy does not assume anything about the nature
of the traffic between a client and the remote server. To achieve this goal,
two non-blocking sockets are used in each thread; one for connecting to the client
and one for connecting to the remote server. Whenever there is incoming data on a
socket, 'select' function returns that socket. If there is incoming data from the
client, that data is immediately forwarded to the remote server. With the same
logic, if there is incoming data from the server, data is forwarded to the client.

### Usage

Run the script and wait for incoming clients:   
`$ ./proxy.py local_ip local_port remote_ip remote_port`               
*local_ip* and *local_port* is the address the proxy will bind to.   
*remote_ip* and *remote_port* is the address of the remote TCP server.  
