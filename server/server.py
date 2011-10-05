import select
import socket
import threading
import sys
from PyQt4 import QtCore, QtGui
from serverwindow import Ui_Form
import pickle

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
    self.username = ''

  def run(self): #when the client thread is started
    usn = self.client.recv(self.size)
    if connections.has_key(usn):
      self.client.send('REJECT') #TODO and terminate this client!!
      self.client.close()
      return #XXX guessing.

    self.client.send('ACCEPT')

    self.username = usn
    connections[self.username] = self.client #username, socket pair
    
    self.emit(QtCore.SIGNAL("updateUserlist"), None)

    while self.running:
      try:
        data = self.client.recv(self.size)
      except socket.error as (number,msg):
        del connections[self.address]
        self.emit(QtCore.SIGNAL("updateUserlist"), None) #send data as test
        self.emit(QtCore.SIGNAL("updateText"), (self.username + " has disconnected"))
        return

      if data:
        cmd, host, msg = self.parse(data)
        
        if cmd == r'\search':
          pass
        elif cmd == r'\msg':
          self.whisper(host, msg)
        else:
          self.send_all(data)
          self.emit(QtCore.SIGNAL("updateText"), (self.username + " sends msg " + data))
   
      else: #NO DATA
        del connections[self.username]
        self.emit(QtCore.SIGNAL("updateUserlist"), None) #send data as test
        self.emit(QtCore.SIGNAL("updateText"), (self.username + " has disconnected"))
        self.running = 0

  def send_all(self, msg):
    for socket in connections.values():
      try:
        socket.send(self.username+': '+msg)
      except IOError: 
        print 'Socket already closed'

  def whisper(self, host, msg):
    if connections.has_key(host):
      connections[host].send("whisper from "+self.username+":"+msg)
      self.client.send("whisper to "+host+": "+msg)
    else:
      self.client.send("Sorry you cannot whisper to "+host+" because they do not exist")

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
    except:
      print 'No host'
  
    try:
      msg = sdata[2]
    except:
      print 'No msg'

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

    for i in connections.keys(): #update my userlist
      item = QtGui.QListWidgetItem(str(i))
      self.ui.listWidget.addItem(item) 

    userlist = pickle.dumps(connections.keys()) 

    for socket in connections.values(): #send the updated userlist
      try:
        socket.send(userlist)
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

