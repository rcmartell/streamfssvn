import sys, time
from mftparser import MFTParser



def main():
    parser = MFTParser(sys.argv[1])
    parser.setup_mft_data()
    parser.parse_mft()


if __name__ == "__main__":
    start = time.time()
    main()
    duration = int(time.time()) - start
    print "Duration: {0:02d}:{1:02d}".format((int(duration / 60) % 60), int(duration % 60))