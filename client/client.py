#!/usr/bin/env python

"""
An echo client that allows the user to send multiple lines to the server.
Entering a blank line will exit the client.
"""

import socket
import sys
import select

class Client:

    def __init__(self, ip, port):
        self.host = ip
        self.port = port 
        self.size = 1024
        self.socket = None
        self.username = ''

    def open_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    def close_socket(self):
        self.socket.close()

    def send(self, message):
        self.socket.send(message)
         
if __name__ == '__main__':

    c = Client(sys.argv[1], int(sys.argv[2]))

    if c.request_username():
        c.run()
    else:
        print 'Something went wrong, restart client.'

