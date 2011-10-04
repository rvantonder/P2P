import select
import socket
import threading
import sys
from PyQt4 import QtCore, QtGui
from serverwindow import Ui_Form

global connections
global calls #calls will be a list that contains n-tuples, each of which corresponds to a conference in progress

class Client(QtCore.QThread):
  def __init__(self,(client,address)):
    QtCore.QThread.__init__(self,None) #parent = none
    self.client = client #client, hostname?
    self.address = address[0] 
    self.port = str(address[1])
    self.size = 1024
    self.running = 1

  def run(self): #when the client thread is started
    connections[self.address] = self.client
    self.emit(QtCore.SIGNAL("updateUserlist"), None)

    try:
      self.client.send("ul__ "+' '.join(connections.keys())+"\n")
      self.emit(QtCore.SIGNAL("updateText"), (self.address + " has connected"))
    except socket.error:
      print 'failed sending userlist'

    while self.running:
      try:
        data = self.client.recv(self.size)
      except socket.error as (number,msg):
        print number,msg
        print 'Socket error on receive'
        for conference in calls: #TODO fix if already in call
          if self.address in conference:
            conference.remove(self.address) #remove myself from the call/conference
            if len(conference) == 1: #if there are less than two involved in the call
              connections[conference[0]].send("dc__\n") #send the other host a dc__ command
              self.emit(QtCore.SIGNAL("updateText"), (conference[0] + " has been prompted to disconnect "))
              calls.remove(conference) #delete the entire call if there is only one active member 
            elif len(conference) > 1:
              for i in conference:
                connections[i].send(i+" has disconnected from the call\n")

        print self.address,"removed from calls IN EXCEPTION"
        print "calls:"
        print calls


        del connections[self.address]
        self.emit(QtCore.SIGNAL("updateUserlist"), None) #send data as test
        self.emit(QtCore.SIGNAL("updateText"), (self.address + " has disconnected"))
        return

      if data:
        cmd, host, msg = self.parse(data)
        
        if cmd == r'\call':
          if self.address == host:
            connections[self.address].send("You cannot call yourself\n")
            break #TODO confirm working

          self.emit(QtCore.SIGNAL("updateText"), (self.address + " wants to call " + host))
          if host in connections.keys(): #TODO add callers to conferences
            if self.host_in_call(host) or self.host_in_call(self.address): #check if either in call already
              self.emit(QtCore.SIGNAL("updateText"), ("already in calls"))
              connections[self.address].send("A call is already active, use \callc\n")
              connections[host].send("A call is already active, use \callc\n")
            else:
              self.emit(QtCore.SIGNAL("updateText"), (host + " found"))
              connections[self.address].send("ca__ "+host+"\n") #todo add call state variable
              connections[host].send("ca__ "+self.address+"\n")
              calls.append([self.address,host]) #append the call/conference
              connections[self.address].send("You are now in a call with "+host+"\n")
              connections[host].send("You are now in a call with "+self.address+"\n")
            
            #connect procedure
          else:
            self.emit(QtCore.SIGNAL("updateText"), (host + " not found"))
            self.client.send("The host you wish to call does not exist\n")
        elif cmd == r'\msg':
          self.whisper(host, msg)
        elif cmd == r'\dc':
          print 'Current calls'
          print calls
          self.emit(QtCore.SIGNAL("updateText"), (self.address + " wants to disconnect a call "))

          for conference in calls: 
            if self.address in conference:
              conference.remove(self.address) #remove myself from the call/conference
              connections[self.address].send("dc__\n")
              self.emit(QtCore.SIGNAL("updateText"), (self.address + " has been prompted to disconnect "))
              if len(conference) == 1: #if there are less than two involved in the call
                connections[conference[0]].send("dc__\n") #send the other host a dc__ command
                self.emit(QtCore.SIGNAL("updateText"), (conference[0] + " has been prompted to disconnect "))
                calls.remove(conference) #delete the entire call if there is only one active member 
              elif len(conference) > 1:
                for i in conference:
                  connections[i].send(i+" has disconnected from the call\n")

          print 'Removed calls'
          print calls

        elif cmd == r'\callc':
          if self.host_in_call(host): #check if in call already
            self.emit(QtCore.SIGNAL("updateText"), (self.address + "attempting conference call with " + host))
            self.join_host_call(host)
            channel_c = self.get_channel(host)
            connections[self.address].send("You are now in a conference call with "+', '.join(channel_c)+"\n")
            for h in channel_c:
              connections[h].send("Adding "+self.address+" to the call\n")
          else:
            connections[self.address].send("There is no call active, you cannot make a conference call, use \call\n")

          
        else:
          self.send_all(data)
          self.emit(QtCore.SIGNAL("updateText"), (self.address + " sends msg " + data))
   
      else: #NO DATA
        del connections[self.address]

        for conference in calls: #TODO fix if already in call
          if self.address in conference:
            conference.remove(self.address) #remove myself from the call/conference
            if len(conference) == 1: #if there are less than two involved in the call
              connections[conference[0]].send("dc__\n") #send the other host a dc__ command
              self.emit(QtCore.SIGNAL("updateText"), (conference[0] + " has been prompted to disconnect "))
              calls.remove(conference) #delete the entire call if there is only one active member 
            elif len(conference) > 1:
              for i in conference:
                connections[i].send(i+" has disconnected from the call\n")


        print self.address,"removed from calls"
        print "calls:"
        print calls

        self.emit(QtCore.SIGNAL("updateUserlist"), None) #send data as test
        self.emit(QtCore.SIGNAL("updateText"), (self.address + " has disconnected"))
        self.running = 0

  def host_in_call(self, host):
    for conference in calls:
      if host in conference:
        return True

    return False

  def get_channel(self, host):
    for conference in calls:
      if host in conference:
        return conference

  def join_host_call(self, host):
    print "Adding",self.address,"to calls"
    for conference in calls:
      if host in conference:
        conference.append(self.address)
    print "calls:"
    print calls

  def send_all(self, msg):
    for socket in connections.values():
      try:
        socket.send(self.address+': '+msg+'\n')
      except IOError: 
        print 'Socket already closed'

  def whisper(self, host, msg):
    if connections.has_key(host):
      connections[host].send("whisper from "+self.address+":"+msg+"\n")
      self.client.send("whisper to "+self.address+":"+msg+"\n")
    else:
      self.client.send("Sorry you cannot whisper to "+host+" because they do not exist"+"\n")

  def parse(self, data):
    
    cmd = "" 
    host = ""
    msg = ""
    try:
      sdata = data.split(" ")
    except:
      pass

    try:
      cmd = sdata[0]
    except:
      print 'No cmd index'
    
    try:
      host = sdata[1]
      host.rstrip()
    except:
      print 'No host'
  
    try:
      msg = data[len(cmd)+len(host):]
    except:
      print 'No msg'

    if not cmd == r'\call' and not cmd == r'\msg':
      if cmd.startswith(r'\\'):
        self.emit(QtCore.SIGNAL("updateText"), ("command " + cmd + " from " + self.address + " not valid"))

    return cmd, host, msg
       
class ServerGUI(QtGui.QWidget):
  def __init__(self,port):

    super(ServerGUI, self).__init__()

    self.ui = Ui_Form()
    self.ui.setupUi(self)
    
    self.host = ''
    self.port = port
    self.backlog = 5
    self.size = 1024
    self.socket = None
    self.threads = []

    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.bind((self.host,self.port))
      self.socket.listen(self.backlog)
    except socket.error:
      print "Could not open port. Aborting."
      sys.exit(1)

    self.c = None

  def run(self):
    input = [self.socket,sys.stdin]
    running = 1

    while running:
        inputready,outputready,exceptready = select.select(input,[],[])

        for s in inputready: #the polling loop, between sockets and stdin

            if s == self.socket:
                c = Client(self.socket.accept())
                self.connect(c, QtCore.SIGNAL("updateUserlist"), self.updateUserlist)
                self.connect(c, QtCore.SIGNAL("updateText"), self.updateText)
                c.start()
                self.threads.append(c)

            elif s == sys.stdin:
                junk = sys.stdin.readline()
                running = 0

  def updateUserlist(self):
    self.ui.listWidget.clear()

    for i in connections.keys():
      item = QtGui.QListWidgetItem(str(i))
      self.ui.listWidget.addItem(item) 

    for socket in connections.values(): #send the updated userlist
      try:
        socket.send("ul__ "+' '.join(connections.keys())+"\n")
      except IOError: 
        print 'Socket already closed'
    
  def updateText(self, msg):
    self.ui.textEdit.append(msg)
    self.ui.textEdit.ensureCursorVisible()


if __name__ == '__main__':

  connections = {}
  calls = []

  try:
    app = QtGui.QApplication(sys.argv)
    gui = ServerGUI(int(sys.argv[1]))
    t = threading.Thread(target=gui.run)
    t.setDaemon(True)
    t.start()
    gui.show()
    sys.exit(app.exec_())
  except IndexError:
    print 'Usage: python voip_server.py <port>'

