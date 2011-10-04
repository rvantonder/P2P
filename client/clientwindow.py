# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'archat.ui'
#
# Created: Tue Jul 26 11:59:55 2011
#      by: PyQt4 UI code generator 4.7.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(518, 189)
        Form.setWindowIcon(QtGui.QIcon('tray.png'))
        self.listWidget = QtGui.QListWidget(Form)
        self.listWidget.setGeometry(QtCore.QRect(340, 10, 171, 171))
        self.listWidget.setAutoFillBackground(False)
        self.listWidget.setStyleSheet("color: rgb(0, 85, 0)")
        self.listWidget.setObjectName("listWidget")
        self.textEdit = QtGui.QTextEdit(Form)
        self.textEdit.setGeometry(QtCore.QRect(0, 10, 331, 141))
        self.textEdit.setAutoFillBackground(True)
        self.textEdit.setStyleSheet("color: rgb(0, 0, 255)")
        self.textEdit.setFrameShadow(QtGui.QFrame.Sunken)
        self.textEdit.setReadOnly(True)
        self.textEdit.setObjectName("textEdit")
        self.lineEdit = QtGui.QLineEdit(Form)
        self.lineEdit.setGeometry(QtCore.QRect(0, 160, 331, 20))
        self.lineEdit.setMaxLength(100) #TODO, but to be safe...
        self.lineEdit.setObjectName("lineEdit")
        self.lineEdit.setText("Enter username")
        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(QtGui.QApplication.translate("Form", "archat", None, QtGui.QApplication.UnicodeUTF8))

