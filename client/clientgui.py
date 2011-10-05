#!/usr/bin/env python

import sip
sip.setapi('QVariant', 2)
import sys
import select
import threading
import socket
import pickle
import os

from PyQt4 import QtCore, QtGui
from clientwindow import Ui_Form

"""
The Client GUI class.
"""

class ClientForm(QtGui.QWidget):
  def __init__(self, host, port, usn):
    super(ClientForm, self).__init__()
    self.ui = Ui_Form()
    self.ui.setupUi(self)
    self.ui.lineEdit.setFocus()
    self.icon = QtGui.QIcon('creeper.tif')
    self.colour_list = (QtCore.Qt.red, QtCore.Qt.darkRed, QtCore.Qt.blue, QtCore.Qt.darkGreen, QtCore.Qt.magenta, QtCore.Qt.darkBlue, QtCore.Qt.darkCyan,QtCore.Qt.darkMagenta, QtCore.Qt.darkYellow, QtCore.Qt.darkGray, QtGui.QColor('#00CC99'), QtGui.QColor('#0099FF'), QtGui.QColor('#005555'), QtGui.QColor('#FF6600'), QtGui.QColor('#660033'), QtGui.QColor('#9900FF'))
    self.user_colour_list = {}
    self.running = 1

    self.pbar = QtGui.QProgressBar(self)
#    self.pbar.initStyleOption(QtGui.QMacStyle)
    self.pbar.setOrientation(QtCore.Qt.Vertical)
    self.pbar.setGeometry(0, 0, 30, 200)

    self.host = host
    self.port = port
    self.size = 1024
    self.socket = None
    self.username = ''

    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.connect((self.host, self.port))
    except socket.error:
      print 'Not accepting connections'
      sys.exit(1)

    try:
      self.socket.send(usn)
      response = self.socket.recv(self.size)
      if response == 'ACCEPT':
        self.username = usn
      else:
        print 'Username already exists, please choose a different username'
        sys.exit(1)
    except socket.error:
      print 'Some socket error'

    self.receiver = Receiver(self.socket)
    self.connect(self.receiver, QtCore.SIGNAL("update_msg"), self.update_msg)
    self.connect(self.receiver, QtCore.SIGNAL("update_userlist"), self.update_userlist)
    self.receiver.start() #start listening

    #self.downloader = Downloader()

  def on_lineEdit_returnPressed(self):
    if self.ui.lineEdit.displayText() != '':
      stringToSend = self.ui.lineEdit.displayText()

      try:
        self.socket.send(str(stringToSend)) 
      except socket.error:
        self.ui.textEdit.setTextColor(QtCore.Qt.black)
        self.ui.textEdit.setText('The connection with the server has been lost, please restart the client.')
        self.ui.listWidget.clear() #delete the whole thing
              
    self.ui.lineEdit.setText('')

  def update_userlist(self, l):
    print 'l',l
    self.ui.listWidget.clear()

    for i in l:
      n = QtGui.QListWidgetItem(self.icon, str(i))
      self.ui.listWidget.addItem(n)

  def update_msg(self, msg):
    self.ui.textEdit.append(msg)
    self.ui.textEdit.ensureCursorVisible()

  def update_progressbar(self, value):
    pass

class Receiver(QtCore.QThread):
  def __init__(self, socket):
    parent = None
    QtCore.QThread.__init__(self, parent)
    self.socket = socket
    self.size = 1024
    self.running = 1

  def run(self):
    while self.running: 
      try:
        response = self.socket.recv(self.size)
        if not response:
          self.socket.close()
          self.emit(QtCore.SIGNAL("update_msg"), 'A connection error occurred, disconnected')
        else:
          display = self.parse_message(response)
          if not display == None:
            self.emit(QtCore.SIGNAL("update_msg"), display)
      except socket.error:
        print 'Unexpected error, disconnecting'
        self.socket.close()
        return

    self.socket.close()

  def parse_message(self, response):

    if response.startswith('(l'): #pickled userlist
      userlist = pickle.loads(response)
      print 'userlist',userlist
      userlist.sort()

      self.emit(QtCore.SIGNAL("update_userlist"), userlist)
      return None

    self.emit(QtCore.SIGNAL("update_msg"), response)

class Downloader(QtCore.QThread):
  def __init__(self):
    parent = None
    QtCore.QThread.__init__(self, parent)

  def download():
    pass
    #calculate amount downloaded out of total
    #self.emit(QtCore.SIGNAL("update_progressbar"), value)


    """
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
      print 'no cmd index'
    
    try:
      host = sdata[1]
      host.rstrip()
    except:
      print 'no host'
       
    try:
      msg = data[len(cmd)+len(host):]
    except:
      print 'no msg'

    if not cmd == r'\msg':
    """
      
    

if __name__ == '__main__':
  gui = ClientForm('localhost',3001)

  t = threading.Thread(target=gui.run)
  t.setDaemon(True) #Sometimes programs spawn a thread as a daemon that runs without blocking the main program from exiting. Using daemon threads is useful for services where there may not be an easy way to interrupt the thread or where letting the thread die in the middle of its work does not lose or corrupt data
  t.start()
  gui.show()
  sys.exit(app.exec_())
