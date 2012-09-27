package solrindexer;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import org.apache.solr.client.solrj.impl.ConcurrentUpdateSolrServer;

public class FileIndexRunner
{
    public static ConcurrentUpdateSolrServer solr;
    public static void main(String[] args) throws Exception
    {
        List<File> files = new ArrayList<File>();
        List<List<File>> threadFiles = new ArrayList<List<File>>();
        String dir = args[0];
        String ext = "";
        String url = "http://localhost:8983/solr";
        int nthreads = 24;
        try
        {
            ext = args[1];
            nthreads = Integer.parseInt(args[2]);
            url = args[3];
        }
        catch(Exception e){}

        walk(new File(dir), ext, files);
        try
        {
            List<Thread> threads = new ArrayList<Thread>();
            for(int i=0; i < nthreads; i++)
            {
                threadFiles.add(new ArrayList<File>());
                for(int j=i; j < files.size(); j += nthreads)
                    threadFiles.get(i).add(files.get(j));
                threads.add(new Thread(new FileIndexer(threadFiles.get(i), url)));
            }
            for(Thread t : threads)
                t.start();
            for(Thread t : threads)
                t.join();
        }catch(Exception e){}
    }

    public static void walk(File dir, String ext, List<File> files)
    {
        File listFile[] = dir.listFiles();
        if(listFile != null)
        {
            for(int i = 0;i < listFile.length;i++)
            {
                if(listFile[i].isDirectory())
                {
                    walk(listFile[i], ext, files);
                }
                else
                {
                    if(ext.equals(""))
                        files.add(listFile[i]);
                    else if(listFile[i].getName().endsWith(ext))
                    {
                        files.add(listFile[i]);
                    }
                }
            }
        }
    }

}
