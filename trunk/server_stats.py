from __future__ import division
import sys, os, threading, string, time
import curses
from curses import *
from psutil import *
from datetime import timedelta

KB = 1024
MB = KB * KB
GB = KB * MB
MINUTE = 60
HOUR = 3600

class Server_Stats():
    def __init__(self, host=None, basepath=None):
        self.host = host
        self.basepath = basepath
        self.filetypes = ['Image', 'PDF', 'Video', 'Application', 'System', 'Audio', 'Text', 'HTML', 'Other']
        self.filedb = dict([(x, {'count' : 0, 'size' :0}) for x in self.filetypes])
        self.totalcount = 0
        self.totalsize = 0
        self.elapsedtime = 0
        self.txspeed = 0
        self.pid = os.getpid()
        self.process = Process(self.pid)
        self.exit = False
        self.time = 0
        thread = threading.Thread(target=self.setupScreen)
        thread.start()
        
    
    def addFile(self, filetype, fsize):
        self.filedb[filetype]['count'] += 1
        self.filedb[filetype]['size'] += int(fsize / KB)
        self.totalcount += 1
        self.totalsize += fsize
    

    def updateStats(self):
        basetime = int(time.time())
        prevtime = basetime
        while not self.exit:
            self.screen.addstr(1, 25, " " * 5, curses.A_NORMAL)
            self.screen.addstr(1, 25, "%0.1f" % self.process.get_cpu_percent(), curses.A_NORMAL)
            self.screen.addstr(1, 39, "[ Used: %i" % int(used_phymem()/1024), curses.A_NORMAL)
            self.screen.addstr(1, 55, "Free: %i ]" % int(avail_phymem()/1024), curses.A_NORMAL)
            yoffset = 7
            for key in self.filedb.keys():
                self.screen.addstr(yoffset, 21, str(self.filedb[key]['count']).rjust(7, " "), curses.A_NORMAL)
                self.screen.addstr(yoffset, 36, str(self.filedb[key]['size']).rjust(7, " ") + " KB", curses.A_NORMAL)
                try:
                    self.screen.addstr(yoffset, 56, "%0.4f" % (self.filedb[key]['count'] / self.totalcount), curses.A_NORMAL)
                except:
                    self.screen.addstr(yoffset, 56, "0".rjust(6, " "), curses.A_NORMAL)
                yoffset += 1
            self.screen.addstr(17, 21, str(self.totalcount).rjust(7, " "), curses.A_NORMAL)
            self.screen.addstr(17, 36, str(int(self.totalsize / KB)).rjust(7, " ") + " KB", curses.A_NORMAL)
            self.elapsedtime = int(time.time() - basetime)
            self.screen.addstr(19, 21, str(timedelta(seconds=self.elapsedtime)), curses.A_NORMAL)
            try:
                self.txspeed = (self.totalsize / self.elapsedtime) / MB
            except:
                self.txspeed = 0
            self.screen.addstr(20, 21, " " * 20, curses.A_NORMAL)
            self.screen.addstr(20, 21, "%0.1f".rjust(6, " ") % self.txspeed + "MB", curses.A_NORMAL)
            prevtime = self.elapsedtime
            self.screen.refresh()
            time.sleep(1)
    
    def key_handler(self):
        while True:
            c = self.screen.getch()
            if c in (curses.KEY_END, ord('!')):
                self.exit = True
                break
        
    def setupScreen(self):
        stdscr=curses.initscr()
        try:
            curses.curs_set(0)
        except:
            pass
        curses.noecho() ; curses.cbreak()
        stdscr.keypad(1)
        self.screen = stdscr.subwin(23, 72, 0, 0)
        self.screen.clear()
        self.screen.box()
        self.screen.hline(2, 1, curses.ACS_HLINE, 70)
        self.screen.addstr(1, 2, "StreamFS Client", curses.A_STANDOUT)
        self.screen.addstr(1, 20, "CPU:", curses.A_BOLD)
        self.screen.addstr(1, 31, "Memory:", curses.A_BOLD)
        self.screen.addstr(3, 2, "File statistics:", curses.A_BOLD)
        self.screen.addstr(5, 2, "Type", curses.A_BOLD)
        self.screen.addstr(5, 22, "Count", curses.A_BOLD)
        self.screen.addstr(5, 36, "Total Size", curses.A_BOLD)
        self.screen.addstr(5, 54, "Count/Total", curses.A_BOLD)
        yoffset = 7
        for key in self.filedb.keys():
            self.screen.addstr(yoffset, 2, string.capitalize(key), curses.A_BOLD)
            yoffset += 1
        self.screen.addstr(16, 2, "-" * 68, curses.A_BOLD)
        self.screen.addstr(17, 2, "Total:", curses.A_BOLD)
        self.screen.addstr(19, 2, "Elapsed Time:", curses.A_BOLD)
        self.screen.addstr(20, 2, "Average Speed:", curses.A_BOLD)
        self.updateThread = threading.Thread(target=self.updateStats)
        self.inputListener = threading.Thread(target=self.key_handler)
        self.updateThread.start()
        self.inputListener.start()
        self.updateThread.join()
        self.inputListener.join()

        
if __name__=='__main__':
    stats = Server_Stats()
    stats.setupScreen(stdscr)
    stdscr.keypad(0)
    curses.echo() ; curses.nocbreak()
    curses.endwin()
    stdscr.keypad(0)
    curses.echo() ; curses.nocbreak()
    curses.endwin()
