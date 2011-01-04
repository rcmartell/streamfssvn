from PyQt4 import QtCore, QtGui
import Pyro.core, Pyro.naming
from pyqonsole import *

class StreamFSGUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.ns = Pyro.naming.locateNS()
        self.server_count = 0
        self.setup(self)

    def setup(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(640, 480)
        self.centralwidget = QtGui.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.selectImage = QtGui.QPushButton(self.centralwidget)
        self.selectImage.setGeometry(QtCore.QRect(240, 50, 75, 20))
        self.selectImage.setObjectName("selectImage")
        self.comandInput = QtGui.QLineEdit(self.centralwidget)
        self.comandInput.setGeometry(QtCore.QRect(20, 10, 211, 20))
        self.comandInput.setObjectName("comandInput")
        self.targetImage = QtGui.QLineEdit(self.centralwidget)
        self.targetImage.setGeometry(QtCore.QRect(20, 50, 211, 20))
        self.targetImage.setAutoFillBackground(True)
        self.targetImage.setReadOnly(True)
        self.targetImage.setObjectName("targetImage")
        self.updateButton = QtGui.QPushButton(self.centralwidget)
        self.updateButton.setGeometry(QtCore.QRect(20, 380, 91, 20))
        self.updateButton.setObjectName("updateButton")
        self.statusView = QtGui.QTextBrowser(self.centralwidget)
        self.statusView.setGeometry(QtCore.QRect(340, 10, 281, 361))
        self.statusView.setObjectName("statusView")
        self.line = QtGui.QFrame(self.centralwidget)
        self.line.setGeometry(QtCore.QRect(320, 10, 16, 361))
        self.line.setFrameShape(QtGui.QFrame.VLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName("line")
        self.progressBar = QtGui.QProgressBar(self.centralwidget)
        self.progressBar.setGeometry(QtCore.QRect(20, 410, 611, 23))
        self.progressBar.setProperty("value", 0)
        self.progressBar.setObjectName("progressBar")
        self.runButton = QtGui.QPushButton(self.centralwidget)
        self.runButton.setGeometry(QtCore.QRect(240, 10, 75, 20))
        self.runButton.setObjectName("runButton")
        self.serverList = QtGui.QTableWidget(self.centralwidget)
        self.serverList.setGeometry(QtCore.QRect(20, 90, 291, 281))
        self.serverList.setAlternatingRowColors(True)
        self.serverList.setRowCount(10)
        self.serverList.setColumnCount(3)
        self.serverList.setHorizontalHeaderLabels(['name', 'address', 'port'])
        self.serverList.verticalHeader().setVisible(False)
        self.serverList.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
        self.serverList.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.serverList.setObjectName("serverList")
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QtGui.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.menubar = QtGui.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 640, 21))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtGui.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        MainWindow.setMenuBar(self.menubar)
        self.actionOpen = QtGui.QAction(MainWindow)
        self.actionOpen.setObjectName("actionOpen")
        self.actionExit = QtGui.QAction(MainWindow)
        self.actionExit.setObjectName("actionExit")
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menubar.addAction(self.menuFile.menuAction())
        self.connect(self.selectImage, QtCore.SIGNAL('clicked()'), self.selectTargetImage)
        self.connect(self.updateButton, QtCore.SIGNAL('clicked()'), self.updateServerList)

        self.retranslateUi(MainWindow)
        QtCore.QObject.connect(self.actionExit, QtCore.SIGNAL("triggered()"), MainWindow.close)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QtGui.QApplication.translate("MainWindow", "MainWindow", None, QtGui.QApplication.UnicodeUTF8))
        self.selectImage.setText(QtGui.QApplication.translate("MainWindow", "Select Image", None, QtGui.QApplication.UnicodeUTF8))
        self.updateButton.setText(QtGui.QApplication.translate("MainWindow", "Update", None, QtGui.QApplication.UnicodeUTF8))
        self.runButton.setText(QtGui.QApplication.translate("MainWindow", "Run", None, QtGui.QApplication.UnicodeUTF8))
        self.menuFile.setTitle(QtGui.QApplication.translate("MainWindow", "File", None, QtGui.QApplication.UnicodeUTF8))
        self.actionOpen.setText(QtGui.QApplication.translate("MainWindow", "Open", None, QtGui.QApplication.UnicodeUTF8))
        self.actionExit.setText(QtGui.QApplication.translate("MainWindow", "Exit", None, QtGui.QApplication.UnicodeUTF8))

    def selectTargetImage(self):
        self.image = QtGui.QFileDialog.getOpenFileName()
        self.targetImage.setText(self.image)

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
    app = QtGui.QApplication(sys.argv)
    gui = StreamFSGUI()
    gui.show()
    app.exec_()