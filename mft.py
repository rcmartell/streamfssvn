
__all__ = ["MFT_ENTRY", "FILE_RECORD", "MFT_STANDARD_HEADER", "STANDARD_INFO", "FILENAME", "OBJECT_ID", "INDEX_ROOT", "INDEX_ALLOC", "INDEX_BLOCK", "INDEX_ENTRY", "SECURE_FILE", "SECURITY_DESCRIPTOR", "DATA_ATTR"]

class MFT_ENTRY():
    """Object representing a standard MFT Entry"""
    __slots__ = ("entry_num", "std_info", "attr_list", "filename", "object_id", "sec_file", "idx_root", "idx_alloc", "data", "bitmap")
    def __init__(self, _entry_num=None, _std_info=None, _attr_list=None, _filename=None, _object_id=None,
                 _sec_file=None, _idx_root=None, _idx_alloc=None, _data=None, _bitmap=None):
        self.entry_num = _entry_num
        self.std_info = _std_info
        self.attr_list = _attr_list
        self.filename = _filename
        self.sec_file = _sec_file
        self.object_id = _object_id
        self.idx_root = _idx_root
        self.idx_alloc = _idx_alloc
        self.data = _data
        self.bitmap = _bitmap

class FILE_RECORD(object):
    __slots__=("name", "entry_num", "parent", "ctime", "mtime", "atime", "size", "clusters", "res_data")
    def __init__(self, _name=None, _entry_num=0, _parent=None, _ctime=None, _mtime=None, _atime=None, _size=None, _clusters=None, _res_data=None):
        self.name = _name
        self.entry_num = _entry_num
        self.parent = _parent
        self.ctime = _ctime
        self.mtime = _mtime
        self.atime = _atime
        self.size = _size
        self.clusters = _clusters
        self.res_data = _res_data

class MFT_STANDARD_HEADER():
    """Standard MFT Entry header. All entries should start with one...Should..."""
    __slots__ = ("lsn", "seq_num", "lnk_cnt", "flags", "entry_num", "mft_base")
    def __init__(self, _lsn=None, _seq_num=None, _lnk_cnt=None, _flags=None, _entry_num=None, _mft_base=None):
        self.lsn = _lsn
        self.seq_num = _seq_num
        self.lnk_cnt = _lnk_cnt
        self.flags = _flags
        self.entry_num = _entry_num
        self.mft_base = _mft_base

class STANDARD_INFO():
    """Standard MAC time info and flags"""
    __slots__ = ("ctime", "mtime", "atime", "flags", "sid")
    def __init__(self, _ctime=None, _mtime=None, _atime=None, _flags=None, _sid=None):
        self.ctime = _ctime
        self.mtime = _mtime
        self.atime = _atime
        self.flags = _flags
        self.sid = _sid

class FILENAME():
    """Standard filename entry info"""
    __slots__ = ("parent", "ctime", "mtime", "atime", "alloc_size", "real_size", "flags", "name", "seq_num", "namespace")
    def __init__(self, _parent=None, _ctime=None, _mtime=None, _atime=None,
                 _alloc_size=None, _real_size=None, _flags=None, _name=None, _seq_num=None, _namespace=None):
        self.parent = _parent
        self.ctime = _ctime
        self.mtime = _mtime
        self.atime = _atime
        self.alloc_size = _alloc_size
        self.real_size = _real_size
        self.flags = _flags
        self.name = _name
        self.seq_num = _seq_num
        self.namespace = _namespace

class OBJECT_ID():
    def __init__(self, _object_id=None):
        self.object_id = _object_id

class INDEX_ROOT():
    __slots__ = ("attr_name", "attr_flags", "attr_id", "idx_size", "header_flags", "idx_entries")
    def __init__(self, _attr_name=None, _attr_flags=None, _attr_id=None, _idx_size=None, _header_flags=None, _idx_entries=[]):
        self.attr_name = _attr_name
        self.attr_flags = _attr_flags
        self.attr_id = _attr_id
        self.idx_size = _idx_size
        self.header_flags = _header_flags
        self.idx_entries = _idx_entries

class INDEX_ALLOC():
    __slots__ = ("attr_name", "attr_flags", "attr_id", "start_vcn", "end_vcn", "data_size", "idx_blocks", "clusters")
    def __init__(self, _attr_name=None, _attr_flags=None, _attr_id=None, _start_vcn=None, _end_vcn=None, _data_size=None, _idx_blocks=[], _clusters=None):
        self.attr_name = _attr_name
        self.attr_flags = _attr_flags
        self.attr_id = _attr_id
        self.start_vcn = _start_vcn
        self.end_vcn = _end_vcn
        self.data_size = _data_size
        self.idx_blocks = _idx_blocks
        self.clusters = _clusters


class INDEX_BLOCK():
    __slots__ = ("log_seq", "idx_block_vcn", "idx_size", "alloc_size", "header_flags", "idx_entries")
    def __init__(self, _log_seq=None, _idx_block_vcn=None, _idx_size=None, _alloc_size=None, _header_flags=None, _idx_entries=[]):
        self.log_seq = _log_seq
        self.idx_block_vcn = _idx_block_vcn
        self.idx_size = _idx_size
        self.alloc_size = _alloc_size
        self.header_flags = _header_flags
        self.idx_entries = _idx_entries

class INDEX_ENTRY():
    __slots__ = ("mft_ref", "flags", "parent_ref", "ctime", "mtime", "atime", "alloc_size", "real_size", "file_flags", "name")
    def __init__(self, _mft_ref=None, _flags=None, _parent_ref=None, _ctime=None, _mtime=None, _atime=None, _alloc_size=None, _real_size=None, _file_flags=None, _name=None):
        self.mft_ref = _mft_ref
        self.flags = _flags
        self.parent_ref = _parent_ref
        self.ctime = _ctime
        self.mtime = _mtime
        self.atime = _atime
        self.alloc_size = _alloc_size
        self.real_size = _real_size
        self.file_flags = _file_flags
        self.name = _name

class SECURE_FILE():
    def __init__(self, _sii=None, _sdh=None, _sds=None):
        self.sii = _sii
        self.sdh = _sdh
        self.sds = _sds

class ATTR_LIST():
    __slots__ = ("nonresident", "size", "init_size", "attr_entries", "clusters")
    def __init__(self, _nonresident=None, _size=None, _init_size=None, _attr_entries=[], _clusters=None):
        self.nonresident = _nonresident
        self.size = _size
        self.init_size = _init_size
        self.attr_entries = _attr_entries
        self.clusters = _clusters

class ATTR_LIST_ENTRY():
    __slots__ = ("attr_type", "attr_len", "start_vcn", "mft_ref", "attr_id", "attr_name")
    def __init__(self, _attr_type=None, _attr_len=None, _name_len=None, _start_vcn=None, _mft_ref=None, _attr_id=None, _attr_name=None):
        self.attr_type = _attr_type
        self.attr_len = _attr_len
        self.name_len = _name_len
        self.start_vcn = _start_vcn
        self.mft_ref = _mft_ref
        self.attr_id = _attr_id
        self.attr_name = _attr_name

class DATA_ATTR():
    __slots__ = ("nonresident", "flags", "attr_id", "start_vcn", "end_vcn", "alloc_size", "data_size", "clusters", "fragmented", "res_data", "attr_name")
    def __init__(self, _nonresident=None, _flags=None, _attr_id=None, _start_vcn=None, _end_vcn=None,
                 _alloc_size=None, _data_size=None, _clusters=None, _fragmented=False, _res_data=None, _attr_name=None):
        self.nonresident = _nonresident
        self.flags = _flags
        self.attr_id = _attr_id
        self.start_vcn = _start_vcn
        self.end_vcn = _end_vcn
        self.alloc_size = _alloc_size
        self.data_size = _data_size
        self.clusters = _clusters
        self.fragmented = _fragmented
        self.res_data = _res_data
        self.attr_name = _attr_name

class BITMAP():
    def __init__(self, _bmap=None):
        self.bmap = _bmap

class SECURITY_DESCRIPTOR():
    def __init__(self, _sacl=None, _dacl=None, _user_sid=None, _group_sid=None):
        self.sacl = _sacl
        self.dacl = _dacl
        self.user_sid = _user_sid
        self.group_sid = _group_sid
