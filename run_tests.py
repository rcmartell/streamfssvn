from subprocess import *
import os

p1 = Popen("start /wait cmd /K python streamclient-test.py s1 C:\\Users\\rob\\streamfs", shell=True)
p2 = Popen("start /wait cmd /K python streamclient-test.py s2 E:\\", shell=True)
p3 = Popen("start /wait cmd /K python imagereader.py E:\\testimg.dd test.dd s1 s2", shell=True)

while True:
    input = raw_input()
    if input == "c":
        Popen("start /wait taskkill /F /PID %d /PID %d /PID %d /T" % (p1.pid, p2.pid, p3.pid), shell=True)
        os._exit(0)

