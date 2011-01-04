from cx_Freeze import setup, Executable

setup(
        name = "MFTParser",
        version = "0.1",
        description = "",
        executables = [Executable("mft_parser.py")])
