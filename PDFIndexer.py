import lucene, sys, os, threading, time


class PDFIndexer():
    def __init__(self, root, storeDir):
        self.root = root
        self.store = lucene.SimpleFSDirectory(lucene.File(storeDir))
        self.analyzer = lucene.StandardAnalyzer(lucene.Version.LUCENE_CURRENT)
        self.writer = lucene.IndexWriter(self.store, self.analyzer, True, lucene.IndexWriter.MaxFieldLength.LIMITED)
        self.writer.setMaxFieldLength(1048576)
    
    
    def indexPDFs(self):
        files = os.listdir(self.root)
        for file in files:
            #os.system('pdfimages -j -q "%s" pics/' % file)
            os.system('pdftotext -q "%s" "%s.txt"' % (file, os.path.splitext(file)[0]))
        for filename in os.listdir(self.root):
            if not filename.endswith('.txt'):
                continue
            #print "indexing", filename
            try:
                path = os.path.join(self.root, filename)
                file = open(path)
                contents = unicode(file.read(), 'iso-8859-1')
                file.close()
                doc = lucene.Document()
                doc.add(lucene.Field("name", filename,
                                     lucene.Field.Store.YES,
                                     lucene.Field.Index.NOT_ANALYZED))
                doc.add(lucene.Field("path", path,
                                     lucene.Field.Store.YES,
                                     lucene.Field.Index.NOT_ANALYZED))
                if len(contents) > 0:
                    doc.add(lucene.Field("contents", contents,
                                         lucene.Field.Store.NO,
                                         lucene.Field.Index.ANALYZED))
                else:
                    print "warning: no content in %s" % filename
                self.writer.addDocument(doc)
            except Exception, e:
                print "Failed in indexDocs:", e
        self.writer.optimize()
        self.writer.close()
                    
                    
if __name__ == '__main__':
    lucene.initVM()
    indexer = PDFIndexer(sys.argv[1], "index")
    indexer.indexPDFs()
                
        