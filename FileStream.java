package solrindexer;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import org.apache.solr.common.util.ContentStreamBase;

public class FileStream extends ContentStreamBase
{
    private final java.io.FileInputStream file;

    public FileStream(String name, Long size, String sourceInfo, final java.io.FileInputStream f) throws IOException
    {
        this.file = f;
        this.contentType = null;
        this.name = name;
        this.size = size;
        this.sourceInfo = sourceInfo;
    }

    @Override
    public Reader getReader() throws IOException
    {
        final String charset = getCharsetFromContentType(this.contentType);
        return charset == null ? new InputStreamReader(this.file)
               : new InputStreamReader(this.file, charset);
    }

    @Override
    public InputStream getStream() throws IOException
    {
        return this.file;
    }
}
