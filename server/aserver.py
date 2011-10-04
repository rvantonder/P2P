#!/usr/bin/env python

import select
import socket
import sys
import threading
import logging
import os
import pickle
import time

global connections

"""
The general server logger
"""

class ServerLogger:
  def __init__(self, logfilename):
    if os.path.isfile(logfilename):
      os.remove(logfilename)

    self.logger = logging.getLogger("serverlogger")
    self.hdlr = logging.FileHandler(logfilename)
    self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(threadName)s %(message)s')
    self.hdlr.setFormatter(self.formatter)
    self.logger.addHandler(self.hdlr)
    self.logger.setLevel(logging.INFO)

"""
Global method used to test if a connection is open
"""    

def isOpen(ip,port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      s.connect((ip, port))
      s.shutdown(2)
      serverLogger.logger.info('port '+str(port)+' open')
    except:
      serverLogger.logger.warn('port '+str(port)+' blocked')

"""
The server class
"""

class Server:
  def __init__(self, port):
    self.host = ''
    self.port = port 
    self.backlog = 5 #maximum 'queue' of connections
    self.size = 1024
    self.socket = None
    self.threads = []

  """
  Opens a socket on the server
  """  

  def open_socket(self):
    serverLogger.logger.info("Attempting to open socket")
    try:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        a = self.socket.bind((self.host,self.port)) #need a reference to it for testing
        b = self.socket.listen(self.backlog)
    except socket.error, (value,message):
        if self.socket:
            self.socket.close()
        serverLogger.logger.warn("Could not open socket")
        sys.exit(1)
    serverLogger.logger.info("Socket open")

  """
  The main loop of the server
  """

  def run(self):
    self.open_socket()
    input = [self.socket,sys.stdin]
    running = 1

    serverLogger.logger.info("Running")
    while running:
        inputready,outputready,exceptready = select.select(input,[],[])

        for s in inputready: #the polling loop, between sockets and stdin

            if s == self.socket:
                serverLogger.logger.info("New connection incoming")  
                c = Client(self.socket.accept())
                c.setDaemon(True)
                c.start()
                self.threads.append(c)

            elif s == sys.stdin:
                # handle standard input
                junk = sys.stdin.readline()
                running = 0

    serverLogger.logger.info('Server shutdown requested.')
    serverLogger.logger.info('Close client sockets.')
    self.close_clients() #tell clients to close open connections, for 'safest' termination
  
    serverLogger.logger.info('Closing server socket')
    self.socket.close()

    serverLogger.logger.info('Terminating client threads')
    for c in self.threads:
        c.join()

    serverLogger.logger.info('Client threads terminated')

  def close_clients(self):
    for socket in connections.values():
      try:
        socket.send('[SERVER]: TERMINATE') 
      except AttributeError:
        serverLogger.logger.info('Socket already terminated')
        

"""
The client class, subclasses thread
"""

class Client(threading.Thread): #client thread
  def __init__(self,(client,address)):
    threading.Thread.__init__(self) 
    self.client = client #the socket
    self.address = address #the address
    self.size = 1024 #the message size
    self.username = None
    self.running = 1 #running state variable

  """
  Parses a message from clients and decides what to do
  """

  def parse_message(self, data):
    temp = data.split(':',1) #will ensure that there are at most two values, otherwise fuckup if more than one colon
    if len(temp) == 2:
        user = temp[0]
        msg = temp[1]
    else: 
        user = 'all'
        msg = temp[0]
    return (user, msg)

  """
  Used to implement the whisper functionality
  """

  def whisper(self, user, msg):
     if connections.has_key(user):
       connections[user].send("whisper from "+self.username+":"+msg)
       connections[self.username].send("whisper to "+user+":"+msg)
     else:
       try:
         self.client.send("Sorry, you cannot whisper to "+user+" because they do not exist") 
       except socket.error:
         serverLogger.logger.info("Server termination") 
  
  """
  Sends a message to all clients from a user
  """

  def send_all(self, user, msg):
     serverLogger.logger.info('Sending message '+msg+' to all')
     for socket in connections.values():
       try:
         socket.send(user+': '+msg)      
       except IOError:
         serverLogger.logger.warn('Socket already closed')

  """
  Sends an updated userlist to all clients
  """

  def update_userlist(self):
    userlist = pickle.dumps(connections.keys()) #use the best you can pickle
    serverLogger.logger.info("Sending pickle")
    self.send_all('[SERVER]',userlist) #the user sending this is nothing

  """
  Main loop of a client thread, recieves and sends data
  """

  def run(self):
    data = self.client.recv(self.size)

    try:
      requested_username = data.split(':')[1] #receive a username request
    except IndexError:
      serverLogger.logger.warn("Client did not adhere to protocol "+data)
      self.client.send('REJECT')
      self.client.close()
      return

    serverLogger.logger.info("Client requested name "+requested_username)

    if connections.has_key(requested_username):
      self.client.send('REJECT') 
      self.client.close() #close the socket
      serverLogger.logger.info("Client username "+requested_username+" rejected: already exists")
      return   
    else:
      self.client.send('ACCEPT')
      
      self.send_all('[SERVER]', requested_username + ' has connected')

      serverLogger.logger.info("Client username "+requested_username+" accepted")
      connections[requested_username]=self.client #add username and connection socket
      self.username = requested_username

      time.sleep(0.1) #test correctness 
      self.update_userlist() #update the user list on connect

    while self.running:
        try:
          data = self.client.recv(self.size)
        except socket.error:
          serverLogger.logger.warn("socket closed on receive")

        if data:
              user, msg = self.parse_message(data)
              serverLogger.logger.info('Parsed message: '+user+' '+msg)
              if user != 'all':
                  self.whisper(user, msg)
              else:
                try:
                  self.send_all(self.username,msg)  
                except socket.error:
                  serverLogger.logger.warn("Server Termination, Closing socket")
                  self.client.close()
                  self.running = 0
        else:
            del connections[self.username] #delete the user; associating socket as value will only work if done as pointer
            self.send_all('[SERVER]', self.username+' has disconnected') 
            self.client.close()
            serverLogger.logger.info(self.username+ 'has disconnected')
            self.update_userlist() #update the user list on disconnect
            serverLogger.logger.info(self.username+' has disconnected')

            self.running = 0

    serverLogger.logger.info("Thread terminating") 

if __name__ == "__main__":
  try:
    connections = {} 
    
    serverLogger = ServerLogger('server.log') 
    serverLogger.logger.info("starting server")
    s = Server(int(sys.argv[1]))
    print 'Hit any key to terminate server'
    s.run() 
  except IndexError:
    print 'Usage: python server.py <port number>'
