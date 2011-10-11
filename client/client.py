#!/usr/bin/env python

import sip
sip.setapi('QVariant', 2)
import sys
import select
import threading
import socket
import pickle
import os
import random
import time
import string

from PyQt4 import QtCore, QtGui
from clientwindow import Ui_Form

"""
The Client GUI class.
"""

global filelist 
global searchresults

class MProgressBar(QtGui.QProgressBar):
  def __init__(self, parent = None):
    QtGui.QProgressBar.__init__(self, parent)
    self.setStyleSheet(MY_BLUE_STYLE) 
    self.setTextVisible(False)

  def setStyle(self, s):
    if s:
      self.setStyleSheet(MY_BLUE_STYLE)
    else:
      self.setStyleSheet(MY_RED_STYLE)

class ClientForm(QtGui.QWidget):
  def __init__(self, host, port, usn):
    super(ClientForm, self).__init__()
    self.ui = Ui_Form()
    self.ui.setupUi(self)
    self.ui.lineEdit.setFocus()
    self.running = 1

    self.dpbar = MProgressBar(self) #download bar
    self.dpbar.setOrientation(QtCore.Qt.Vertical)
    self.dpbar.setGeometry(520, 0, 20, 189)
    self.dpbar.setValue(25)
    self.dpbar.setStyle(False)

    self.upbar = MProgressBar(self) #upload bar
    self.upbar.setOrientation(QtCore.Qt.Vertical)
    self.upbar.setGeometry(545, 0, 20, 189)
    self.upbar.setValue(75)
    self.upbar.setStyle(True)

    self.host = host
    self.port = port
    self.size = 1024
    self.socket = None
    self.username = ''
    
    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.connect((self.host, self.port))
      self.key = int(hash(self.socket)) ^ int(time.time())
      self.key = self.key if self.key > 0 else -self.key
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
    self.connect(self.receiver, QtCore.SIGNAL("update_download_progressbar"), self.update_download_progressbar) #tester method. should be connected to a Downloader object
    self.receiver.start() #start listening

    #self.downloader = Downloader()

  def on_lineEdit_returnPressed(self):
    if self.ui.lineEdit.displayText() != '':
      stringToSend = self.ui.lineEdit.displayText()
      #unfortunately, we must intercept a '/download' request client side, as the server does not store search results for the clients

      if stringToSend.startswith("\download "):
        fileToDownload = stringToSend.split(' ')[1]
        for host in searchresults.keys():
          for result in searchresults[host]:
            if fileToDownload == result:
              stringToSend = "\download "+host+" "+fileToDownload
              self.socket.send(str(stringToSend))
              self.ui.lineEdit.setText('')
              return

      try:
        self.socket.send(str(stringToSend)) 
      except socket.error:
        self.ui.textEdit.setTextColor(QtCore.Qt.black)
        self.ui.textEdit.setText('The connection with the server has been lost, please restart the client.')
        self.ui.listWidget.clear() #delete the whole thing
              
    self.ui.lineEdit.setText('')

  def update_userlist(self, l):
    self.ui.listWidget.clear()

    for i in l:
      n = QtGui.QListWidgetItem(str(i))
      self.ui.listWidget.addItem(n)

  def update_msg(self, msg):
    self.ui.textEdit.append(msg)
    self.ui.textEdit.ensureCursorVisible()

  def update_download_progressbar(self, value):
    self.dpbar.setValue(value)
    v = value
    if not v == 100: #XXX this is ONLY to demonstrate how it would appear. sleeping the thread is NOT a good idea; it defers other GUI events. no idea for a work around right now. its own thread would be overkill.
      while not v == 100:
        time.sleep(.005)
        v += 1
        self.dpbar.setValue(v)
    
  def update_upload_progressbar(self, value):
    self.upbar.setValue(value) 

class Receiver(QtCore.QThread):
  def __init__(self, socket):
    parent = None
    QtCore.QThread.__init__(self, parent)
    self.socket = socket
    self.size = 1024
    self.running = 1
    self.searchers = []

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
            random_value = int(random.random()*100) #XXX tester method
            self.emit(QtCore.SIGNAL("update_download_progressbar"), random_value) #XXX tester method
      except socket.error:
        print 'Unexpected error, disconnecting'
        self.socket.close()
        return

    self.socket.close()

  def parse_message(self, response):

    if response.startswith('(l'): #pickled userlist
      userlist = pickle.loads(response)
      userlist.sort()

      self.emit(QtCore.SIGNAL("update_userlist"), userlist)
      return None
    elif response.startswith('__search'):
      search_identifier = response.split()[1] #the hash
      query = response.split()[2:] #the rest of the query
      print 'search query',query
      s = Searcher(' '.join(query),self.socket,search_identifier)
      s.start()
      self.searchers.append(s) #need to keep reference
      return '<received search request>'
    elif response.startswith('++search'): #am getting a search result back from server
      print 'incoming search result'
      r = response.split(' ')
      print 'splitresult'
      print r
      try:
        searchresults[r[1]].append(pickle.loads(r[2]))
      except KeyError:
        searchresults[r[1]] = []
        searchresults[r[1]].append(pickle.loads(r[2]))
      results = '\n'.join(pickle.loads(r[2])) #the query
      if len(results) > 0:
        self.emit(QtCore.SIGNAL("update_msg"), results)
      return
      
    #self.emit(QtCore.SIGNAL("update_msg"), response)
    return response

class Downloader(QtCore.QThread):
  def __init__(self):
    parent = None
    QtCore.QThread.__init__(self, parent)

  def download():
    pass
    #calculate amount downloaded out of total
    #self.emit(QtCore.SIGNAL("update_progressbar"), value)

class Searcher(QtCore.QThread): #will search for files and return the result to the server. incomplete, not sure if this is the right approach
  def __init__(self, query, socket, search_identifier):
    parent = None
    QtCore.QThread.__init__(self, parent)
    self.query = query
    self.socket = socket
    self.search_identifier = search_identifier
    print 'initialized'

  def run(self): #TODO filter!
    print 'searching list...'
    r = filter(lambda x: not string.find(x.lower(), self.query.lower()) == -1, filelist) #filter out results
    result = pickle.dumps(r)
    #print 'search result', result
    self.socket.send("**search "+self.search_identifier+ " " +result)
      
MY_RED_STYLE = """
QProgressBar{
  border: 2px solid grey;
  border-radius: 5px;
  text-align: center
}

QProgressBar::chunk {
  background-color: #C41336;
  height: 10px;
  margin: 1px;
}
"""    

MY_BLUE_STYLE = """
QProgressBar{
  border: 2px solid grey;
  border-radius: 5px;
  text-align: center
}

QProgressBar::chunk {
  background-color: #1589C1;
  height: 10px;
  margin: 1px;
}
"""    
 
if __name__ == '__main__':
  try:
    searchresults = {}
    filelist = {}
    app = QtGui.QApplication(sys.argv)
    gui = ClientForm(sys.argv[1], int(sys.argv[2]), sys.argv[3])
     
    path = "files/"
    listing = os.listdir(path)
    for infile in listing:
        info = os.stat(path + infile)
        filelist[infile] = info[6]/(1024.**2)

    print 'filelist',filelist

    gui.show()
    sys.exit(app.exec_())
  except IndexError:
    print 'Usage: python main.py <server> <port> <username>'
 
