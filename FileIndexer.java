package solrindexer;

import java.io.File;
import java.io.FileInputStream;
import java.net.MalformedURLException;
import java.util.List;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.solr.client.solrj.SolrServer;
import org.apache.solr.client.solrj.impl.ConcurrentUpdateSolrServer;
import org.apache.solr.client.solrj.request.ContentStreamUpdateRequest;
import org.apache.http.impl.conn.tsccm.ThreadSafeClientConnManager;

public class FileIndexer extends Thread
{
    public List<File> files;
    public SolrServer solr;
    public FileIndexer(List<File> files, String url) throws MalformedURLException
    {
        ThreadSafeClientConnManager manager = new ThreadSafeClientConnManager();
        manager.setDefaultMaxPerRoute(50);
        DefaultHttpClient client = new DefaultHttpClient(manager);
        this.solr = new ConcurrentUpdateSolrServer(url, client, 200, 24);
        this.files = files;
    }

    @Override
    public void run()
    {
        indexFilesSolrCell(this.files);
    }

    public void indexFilesSolrCell(List<File> files)
    {
        ContentStreamUpdateRequest update;
        for(File file: files)
        {
            update = new ContentStreamUpdateRequest("/update/extract");
            try
            {
                FileInputStream f = null;
                try
                {
                    f = new FileInputStream(file);
                    FileStream fileInputStream = new FileStream(file.getName(),
                                                                file.length(), file.toURI().toString(), f);
                    update.addContentStream(fileInputStream);
                    update.setParam("literal.id", file.getName());
                    update.setParam("uprefix", "ignored_");
                    update.setParam("lowernames", "true");
                    update.setParam("fmap.content", "text");
                    update.setParam("fmap.a", "links");
                    update.setParam("fmap.div", "ignored_");
                    this.solr.request(update);
                }
                finally
                {
                    if(f != null)
                    {
                        f.close();
                    }
                }
            }
            catch(Exception e)
            {
            }
        }
        try
        {
            this.solr.commit();
        }
        catch(Exception e)
        {
        }
    }
}
