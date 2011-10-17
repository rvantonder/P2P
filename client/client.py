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
from difflib import *

from PyQt4 import QtCore, QtGui
from clientwindow import Ui_Form

"""
The Client GUI class.
"""

global filelist 
global searchresults
global port
global uprogress #upload bar progress counter
global dprogress #download bar progress counter
global doUpload #can has upload
global path

#Affine Substitution Cipher
def enc(n): return ''.join(map(lambda x: str((a*int(x)+b) % 10), n))
def dec(n): return ''.join(map(lambda x: str((int(x)-b)*a_inverse % 10), n))

a = 7
a_inverse = 3
b = 5

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
    self.dpbar.setValue(0)
    self.dpbar.setStyle(True)

    self.dpbar_thread = Update_dpbar()
    self.connect(self.dpbar_thread, QtCore.SIGNAL("set_dpbar"), self.set_dpbar)
    self.dpbar_thread.start() 
    
    self.upbar = MProgressBar(self) #upload bar
    self.upbar.setOrientation(QtCore.Qt.Vertical)
    self.upbar.setGeometry(545, 0, 20, 189)
    self.upbar.setValue(0)
    self.upbar.setStyle(False)
    
    self.upbar_thread = Update_upbar()
    self.connect(self.upbar_thread, QtCore.SIGNAL("set_upbar"), self.set_upbar)
    self.upbar_thread.start()
    
    self.host = host
    self.port = port
    self.size = 1024
    self.socket = None
    self.username = ''

    self.downloadingFromHost = None

    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.connect((self.host, self.port))
      self.key = int(hash(self.socket)) ^ int(time.time())
      self.key = self.key if self.key > 0 else -self.key
      print 'sample key',self.key
      print 'key encrypted',enc(str(self.key))
      print 'key decrypted',dec(enc(str(self.key)))
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

    self.downloader = Downloader(self.key) #make the downloader listen for incoming download requests
    self.downloader.start()

    self.receiver = Receiver(self.socket, self.key)
    self.connect(self.receiver, QtCore.SIGNAL("update_msg"), self.update_msg)
    self.connect(self.receiver, QtCore.SIGNAL("update_userlist"), self.update_userlist)
    self.receiver.start() #start listening

  
  def on_lineEdit_returnPressed(self):
    if self.ui.lineEdit.displayText() != '':
      stringToSend = str(self.ui.lineEdit.displayText())

      if stringToSend.startswith("\download "):
        fileToDownload = stringToSend.split(' ')[1]
        for host in searchresults.keys():
          for result in searchresults[host]:
            if fileToDownload == result:
              self.downloadingFromHost = host
              stringToSend = "\download "+host+" "+enc(str(self.key))+" "+fileToDownload #host is the hash
              self.socket.send(str(stringToSend))
              self.ui.lineEdit.setText('')
              return
      elif stringToSend.startswith("\pause"): #TODO try?
        print 'downloading from',self.downloadingFromHost
        stringToSend = "\pause "+self.downloadingFromHost
      elif stringToSend.startswith(r'\resume'):
        stringToSend = r'\resume '+self.downloadingFromHost
      
      try:
        if not stringToSend.startswith("\download "):
          self.socket.send(str(stringToSend)) 
        else:
          self.update_msg('This file is not among your search results')
          
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

  def set_dpbar(self, v):
    self.dpbar.setValue(v)

  def set_upbar(self, v):
    self.upbar.setValue(v)


class Update_dpbar(QtCore.QThread):
  def __init__(self):
    parent = None
    QtCore.QThread.__init__(self, parent)

  def run(self):
    while(1):
      time.sleep(.05)
      self.emit(QtCore.SIGNAL("set_dpbar"), int(dprogress[0]))

class Update_upbar(QtCore.QThread):
  def __init__(self):
    parent = None
    QtCore.QThread.__init__(self, parent)

  def run(self):
    while(1):
      time.sleep(.05)
      self.emit(QtCore.SIGNAL("set_upbar"), int(uprogress[0]))
 
class Receiver(QtCore.QThread):
  def __init__(self, socket, key):
    parent = None
    QtCore.QThread.__init__(self, parent)
    self.socket = socket
    self.size = 1024
    self.running = 1
    self.searchers = []
    self.key = key #the client key

    self.uploadSlotOpen = True
    self.uploaders = [] #keeps track of uploaders (threads)

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
      r = response.split(' ')
      pickled_results = pickle.loads(r[2])

      temp_results = []

      try:
        for i in pickled_results:
          if i not in searchresults[r[1]]:
            searchresults[r[1]].append(i)
            temp_results.append(i)
      except KeyError:
        searchresults[r[1]] = []
        for i in pickled_results:
          if i not in searchresults[r[1]]: #TODO double check
            searchresults[r[1]].append(i)
            temp_results.append(i)

      results = '\n'.join(temp_results) #the query
      if len(results) > 0:
        self.emit(QtCore.SIGNAL("update_msg"), results)
      return
    elif response.startswith('++download'): #am getting a download request
      l = response.split(' ')
      key = l[1]
      ffile = l[2]
      address = l[3]
      
      if self.uploadSlotOpen:
        print 'slot open for '+ffile
        uploader = Uploader(key, ffile, address)
        self.connect(uploader, QtCore.SIGNAL("set_ul_flag"), self.setUploadSlotOpen) #allow the downloader to set the slot to open when done downloading

        uploader.start() #start listening
        self.uploaders.append(uploader) #keep reference
        return #don't print the ++download business
      else:
        print 'No download slot'
    elif response.startswith('++pause'):
      doUpload[0] = 0 
      return
    elif response.startswith('++resume'):
      doUpload[0] = 1
      return
        
    return response


  def setUploadSlotOpen(b):
    self.uploadSlotOpen = b

class Downloader(QtCore.QThread): #listens for incoming download requests
  def __init__(self, key):
    parent = None
    QtCore.QThread.__init__(self, parent)
    self.host = '' #bind to localhost
    self.port = port #TODO WAS 3001, NOW ITS THE FOURTH COMMANDLINE ARGUMENT
    self.backlog = 1
    self.size = 1024
    self.socket = None
    self.key = key
    self.downloading = False

    self.conn = None
    self.uploaderAddress = None

    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.bind((self.host, self.port))
      self.socket.listen(self.backlog)
    except socket.error:
      print 'Some problem opening port for Downloader'

  def run(self):
    while 1:
      try:
        self.conn, self.uploaderAddress = self.socket.accept()
      except:
        print '??'

      while 1:
        msg = self.conn.recv(self.size)

        if not msg.startswith('**download'):
          print msg
      
        if msg:
          if msg.startswith('**download'):
            l = msg.split(' ')
            k = l[1] #key
            ffile = l[2] #filename
            fsize = l[3] #filesize

            print 'self.key',self.key,'dec received key',dec(k)

            if str(self.key) == str(dec(k)) and not self.downloading:
              print 'Keys TRUE'
              self.downloading = True
              
              try:
                increment = 100./(float(fsize)*1024.)
              except ValueError:
                print fsize
              print 'increment',increment
            
              dprogress[0] = 0.0
                        
              self.emit(QtCore.SIGNAL("update_download_progressbar"), 0)
              f = open(path[0] + ffile , 'wb', 1)
              while(1):
                data = self.conn.recv(1024)
                if not data:
                    break
                f.write(data)
                dprogress[0] += increment
              f.close()

            else:
              print 'connection rejected'
              self.conn.send("REJECT")
          else: #socket.close??
            print 'Message did not start with **download'
        else:
          print 'No data'
          self.conn.close()
          print 'No more connection'
         
        self.downloading = False
        break

class Uploader(QtCore.QThread):
  def __init__(self, key, filename, address):
    parent = None
    QtCore.QThread.__init__(self, parent)
    self.filename = filename
    self.address = address
    self.socket = None
    self.port = port #TODO Was 3001, NOW ITS THE 4 FOURTH COMMANDLINE ARGUMENT
    self.key = key

  def run(self): #contact originating client with address and key provided by server
    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.connect((self.address, self.port))
    except socket.error as (enum, emsg):
      print enum,emsg
      print 'Uploader could not connect to originating client'

    self.socket.send('**download ' + str(self.key) + ' ' + self.filename + ' ' + str(filelist[self.filename]))

    increment = 100./(float(filelist[self.filename])*1024.)
    uprogress[0] = 0.0
    #self.emit(QtCore.SIGNAL("update_upload_progressbar"), 0)

    f = open(path[0] + self.filename, 'rb')
    while(1):
      while doUpload[0]:
        data = f.read(1024)
        if not data:
            break
        self.socket.send(data)
        uprogress[0] += increment

    f.close()
    self.emit(QtCore.SIGNAL("update_upload_progressbar"), increment)

    self.socket.close()

class Searcher(QtCore.QThread): #will search for files and return the result to the server. incomplete, not sure if this is the right approach
  def __init__(self, query, socket, search_identifier):
    parent = None
    QtCore.QThread.__init__(self, parent)
    self.query = query
    self.socket = socket
    self.search_identifier = search_identifier
    print 'initialized'

  def run(self):
    print 'searching list...'
    r = get_close_matches(self.query.lower(), map(lambda x: x.lower(), filelist))
    result = pickle.dumps(r)
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
    uprogress = []
    uprogress.append(0.0)
    dprogress = []
    dprogress.append(0.0)
    doUpload = []
    doUpload.append(1)

    print 'doupload',doUpload

    port = int(sys.argv[4]) #TODO THIS IS THE PORT ON WHICH THE DOWNLOADER LISTENS, AND THE UPLOADER SENDS TO
    app = QtGui.QApplication(sys.argv)
    gui = ClientForm(sys.argv[1], int(sys.argv[2]), sys.argv[3])
     
    #path = "files/"
    #path = "/var/tmp/"
    path = []
    path.append("/var/tmp/")
    listing = os.listdir(path[0])
    for infile in listing:
        info = os.stat(path[0] + infile)
        filelist[infile] = info[6]/(1024.**2)

    print 'filelist values',filelist.keys()

    gui.show()
    sys.exit(app.exec_())
  except IndexError:
    print 'Usage: python main.py <server> <port> <username>'
 
