# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'streamFS.ui'
#
# Created: Tue May 25 22:34:42 2010
#      by: PyQt4 UI code generator 4.7
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui
import Pyro.core, Pyro.naming

target = None

class QTreeView(QtGui.QTreeView):
    def __init__(self, MainWindow, targetImageLabel):
        QtGui.QTreeView.__init__(self, MainWindow)
        self.mainWindow = MainWindow
        model = QtGui.QFileSystemModel()
        model.setRootPath("/")
        parentIndex = model.index(QtCore.QDir.rootPath())
        self.setModel(model)
        self.setAnimated(True)
        self.setIndentation(20)
        self.hideColumn(1)
        self.targetImage = targetImageLabel
        
    def mouseDoubleClickEvent(self, event):
        item = self.currentIndex()
        target = self.model().fileInfo(item).canonicalFilePath()
        self.targetImage.setText(target)
        QtGui.QTreeView.mouseDoubleClickEvent(self, event)
        


class StreamFSInterface(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.ns = Pyro.naming.locateNS()
        self.server_count = 0
        self.setup(self)
    
    def setup(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        MainWindow.setMaximumWidth(800)
        MainWindow.setMaximumHeight(600)
        self.centralwidget = QtGui.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.comandInput = QtGui.QLineEdit(self.centralwidget)
        self.comandInput.setGeometry(QtCore.QRect(25, 20, 226, 20))
        self.comandInput.setObjectName("comandInput")
        self.updateButton = QtGui.QPushButton(self.centralwidget)
        self.updateButton.setGeometry(QtCore.QRect(25, 480, 86, 20))
        self.updateButton.setObjectName("updateButton")
        self.statusView = QtGui.QTextBrowser(self.centralwidget)
        self.statusView.setGeometry(QtCore.QRect(425, 250, 346, 211))
        self.statusView.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.statusView.setObjectName("statusView")
        self.line = QtGui.QFrame(self.centralwidget)
        self.line.setGeometry(QtCore.QRect(380, 20, 16, 441))
        self.line.setFrameShape(QtGui.QFrame.VLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName("line")
        self.runButton = QtGui.QPushButton(self.centralwidget)
        self.runButton.setGeometry(QtCore.QRect(275, 20, 75, 20))
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("monkey_on_16x16.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.runButton.setIcon(icon)
        self.runButton.setObjectName("runButton")
        self.serverList = QtGui.QTableWidget(self.centralwidget)
        self.serverList.setGeometry(QtCore.QRect(25, 300, 326, 161))
        self.serverList.setObjectName("serverList")
        self.serverList.setShowGrid(False)
        self.serverList.setColumnCount(3)
        self.serverList.setRowCount(10)
        self.serverList.setHorizontalHeaderLabels(['name', 'address', 'port'])
        self.serverList.verticalHeader().setVisible(False)
        self.serverList.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
        self.serverList.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)    
        self.label = QtGui.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(25, 260, 56, 21))
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setWeight(75)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.targetImage = QtGui.QLineEdit(self.centralwidget)
        self.targetImage.setGeometry(QtCore.QRect(85, 260, 271, 21))
        self.targetImage.setCursor(QtCore.Qt.ArrowCursor)
        self.targetImage.setAutoFillBackground(False)
        self.targetImage.setStyleSheet("background-color: rgb(212, 208, 200);")
        self.targetImage.setFrame(False)
        self.targetImage.setReadOnly(True)
        self.targetImage.setObjectName("targetImage")
        self.fileView = QTreeView(self.centralwidget, self.targetImage)
        self.fileView.setGeometry(QtCore.QRect(25, 60, 326, 192))
        self.fileView.setObjectName("fileView")
        self.line_2 = QtGui.QFrame(self.centralwidget)
        self.line_2.setGeometry(QtCore.QRect(425, 210, 346, 16))
        self.line_2.setFrameShape(QtGui.QFrame.HLine)
        self.line_2.setFrameShadow(QtGui.QFrame.Sunken)
        self.line_2.setObjectName("line_2")
        self.fsInfoText = QtGui.QTextEdit(self.centralwidget)
        self.fsInfoText.setGeometry(QtCore.QRect(425, 20, 346, 171))
        self.fsInfoText.setAutoFillBackground(False)
        self.fsInfoText.setStyleSheet("color: rgb(212, 208, 200);\n"
"background-color: rgb(212, 208, 200);")
        self.fsInfoText.setFrameShape(QtGui.QFrame.Box)
        self.fsInfoText.setFrameShadow(QtGui.QFrame.Plain)
        self.fsInfoText.setAutoFormatting(QtGui.QTextEdit.AutoBulletList)
        self.fsInfoText.setReadOnly(True)
        self.fsInfoText.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self.fsInfoText.setObjectName("fsInfoText")
        MainWindow.setCentralWidget(self.centralwidget)
        #self.statusbar = QtGui.QStatusBar(MainWindow)
        #self.statusbar.setObjectName("statusbar")
        #self.statusbar.setSizeGripEnabled(False)
        self.progressBar = QtGui.QProgressBar(self.centralwidget)
        self.progressBar.setProperty("value", 0)
        self.progressBar.setObjectName("progressBar")
        self.progressBar.setGeometry(QtCore.QRect(25, 550, 760, 25))
        #self.statusbar.addPermanentWidget(self.progressBar, 1)
        #MainWindow.setStatusBar(self.statusbar)
        self.menubar = QtGui.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 20))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtGui.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        MainWindow.setMenuBar(self.menubar)
        self.actionOpen = QtGui.QAction(MainWindow)
        self.actionOpen.setObjectName("actionOpen")
        self.actionExit = QtGui.QAction(MainWindow)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap("monkey_off_16x16.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionExit.setIcon(icon1)
        self.actionExit.setObjectName("actionExit")
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menubar.addAction(self.menuFile.menuAction())
        self.updateButton.clicked.connect(self.updateServerList)
        self.retranslateUi(MainWindow)
        QtCore.QObject.connect(self.actionExit, QtCore.SIGNAL("triggered()"), MainWindow.close)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QtGui.QApplication.translate("MainWindow", "StreamFS User Interface", None, QtGui.QApplication.UnicodeUTF8))
        self.updateButton.setText(QtGui.QApplication.translate("MainWindow", "Update", None, QtGui.QApplication.UnicodeUTF8))
        self.runButton.setText(QtGui.QApplication.translate("MainWindow", "Run", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("MainWindow", "Target:", None, QtGui.QApplication.UnicodeUTF8))
        self.fsInfoText.setDocumentTitle(QtGui.QApplication.translate("MainWindow", "File System Info", None, QtGui.QApplication.UnicodeUTF8))
        self.menuFile.setTitle(QtGui.QApplication.translate("MainWindow", "File", None, QtGui.QApplication.UnicodeUTF8))
        self.actionOpen.setText(QtGui.QApplication.translate("MainWindow", "Open", None, QtGui.QApplication.UnicodeUTF8))
        self.actionExit.setText(QtGui.QApplication.translate("MainWindow", "Exit", None, QtGui.QApplication.UnicodeUTF8))
    
    def updateServerList(self):
        count = 0
        servers = self.ns.list()
        for server in servers:
            if server != "Pyro.NameServer":
                full_address = str(self.ns.lookup(server)).split("@")[1]
                address, port = full_address.split(":")
                col1 = QtGui.QTableWidgetItem(server)
                col2 = QtGui.QTableWidgetItem(address)
                col3 = QtGui.QTableWidgetItem(port)
                self.serverList.setItem(count, 0, col1)
                self.serverList.setItem(count, 1, col2)
                self.serverList.setItem(count, 2, col3)
                self.serverList.update()
                count += 1
        


if __name__ == '__main__':
    import sys
    app = QtGui.QApplication([])
    gui = StreamFSInterface()
    gui.show()
    app.exec_()