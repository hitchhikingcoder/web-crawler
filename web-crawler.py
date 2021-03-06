import re
import urllib2
import httplib
import urlnorm
import Queue as Q
import urlparse
import ssl
from ranking_function import BM25
from BeautifulSoup import BeautifulSoup
from pygoogle import pygoogle
from customurllib import customURLlib
from datetime import datetime

'''
  The web crawler class:
  The object of this class takes a query on which the crawling will be focused.
  To start the crawling call the self.crawl() method without any parameters
'''

class WebCrawler:

  def __init__(self,query):
    self.query = query #Search Query
    self.urls = Q.PriorityQueue() # Priority Queue of URLs to be visited and their depth [(score,(url,depth))]
    self.visited = {} # Dictionary keeping track of all the visited URLs
    self.parsed_urls = set() #List to keep track of extracted links in order to avoid repetition
    self.pages_crawled = 0 #Number of pages crawled
    self.valid_mime_types = ["text/html","text/plain","text/enriched"] #Only these MIME types are to be parsed
    self.connectives = ['or','and','is','this']
    self.illegal_extensions = ['cgi','gif','jpg','png','css','js','mp3','mp4','mkv','ppt','doc','pdf','pptx','docx','rar','zip','xls','xlsx']
    self.illegal_folders = ['/cgi-bin/','/images/','/javascripts/','/photos/','/js/','/css/','/stylesheets/']
    self.depth_reached = 0
    self.url_controller = customURLlib()
    self.output_file = open("output.txt",'w+')
    self.fetch_google_results()

  '''
    METHOD FOR GOOGLE SEARCHING
    This method fetches the first 10 google results based on the query passed by the user.
  '''

  def fetch_google_results(self):
    print "Searching Google"
    search = pygoogle(self.query)
    results = search.get_urls()[:10] #Only get the first 10 results
    for result in results:
      print "Google Result: " + str(result)

      if ( self.skip_specific_websites(result) == True ):
        continue

      time = datetime.now().time()
      score,code = self.calculate_BM25_score(result)
      if (not (score == None)) and (code == 200) and (self.is_illegal_folder(result) == False) and (self.is_illegal_extension(result) == False) :
        self.urls.put((score,(str(result),1))) #All google results are at depth 1 with google.com being at depth 0
      self.write_to_file(result,score,int(1),code,time)
      self.pages_crawled += 1

  '''
    Method for calculating the Okapi BM25 score of the webpage
    This method calls the method bm25.BM25Score in the ranking_function file which in turn returns the Okapi BM25 score of the webpage based on the query passed
  '''

  def calculate_BM25_score(self,url):
    req = urllib2.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0' )
    try:
      page = urllib2.urlopen(req)
      code = page.getcode()
      data = page.readlines()
      bm25 = BM25(data,delimiter=' ')
      query = self.query.split()
      score = bm25.BM25Score(query)
      return (score, code)
    except urllib2.HTTPError, err:
      if err.code == 404:
        print "Page not found!"
      elif err.code == 403:
        print "Access denied!"
      else:
        print "Error code: " + str(err.code)
      return (None,err.code)
    except urllib2.URLError, err:
      print "Error: " + str(err.reason)
      return (None, None)
    except httplib.HTTPException:
      print "Error"
      return (None, None)
    except ssl.CertificateError:
      print "SSL CertificateError"
      return (None,None)

  '''
    Method for writing the results to file

    Pattern = "URL | BM25 score | depth | return code | time"
  '''
  def write_to_file(self,url,score,depth,code,time):
    output = url + " | " + str(score) + " | " + str(depth) + " | " + str(code) + " | " + str(time.hour) + ":" + str(time.minute) + ":" + str(time.second) +"\n"
    self.output_file.write(output)

  '''
    Method to check if the URL is an image/javascripts/css/cgi-bin folder
  '''
  def is_illegal_folder(self,url):
    for f in self.illegal_folders:
        if f in url:
          return True
    return False

  '''
    Method to check if the URL has an invalid extension such as .jpg/.css etc.
  '''

  def is_illegal_extension(self,url):
    url_components = urlparse.urlparse(url).path.split('.')
    if len(url_components)>1:
      if url_components[1] in self.illegal_extensions:
        return True
      else:
        return False
    else:
      return False

  '''
    Method for skipping sites like amazon using hardcode
  '''
  def skip_specific_websites(self,url):
    if re.search('\bamazon\b',url):
      return True
    else:
      return False

  '''
    Parse the page and return all the links along with their ranking function score
    The method opens the page and retrieves all the links and adds it to the Priority Queue to be parsed later
  '''

  def parse_page(self,html_document,depth,query):

    soup = BeautifulSoup(html_document)
    new_depth = depth + 1 # Breadth first search depth of the page


    for link in soup.findAll('a', attrs={'href': re.compile("^(http|https)://")}): #Finding all the links with http|https starting
      try:
        href = str(link.get('href')) #The actual link string

        #Check if the link has already been encountered
        if href in self.parsed_urls:
          continue
        else:
          self.parsed_urls.add(href)

        print "Now Crawling: " + str(href)

        '''
          The following checks are performed in the block that follows:

          1. If the URL has already been parsed - Check visited Dictionary
          2. If the URL is an illegal folder as described above
          3. If the URL has an illegal extension as described above
        '''

        if not(href in self.visited) and (self.is_illegal_folder(href) == False) and (self.is_illegal_extension(href) == False) and ( self.skip_specific_websites(href) == False ):

          time = datetime.now().time()

          score, code = self.calculate_BM25_score(href) #BM25 score for the webpage | code = response code

          if (not (score == None)) and (code == 200):
            self.urls.put((score,(href,new_depth)))
            self.pages_crawled += 1

          self.write_to_file(href,score,new_depth,code,time)
      except UnicodeEncodeError:
        print "Error"
        pass


  '''
    Crawl Control Method:

    This method picks a URL from the Priority Queue, opens the URL, checks if it has a valid MIME type and then parses it by calling the method above
  '''
  def crawl(self):
    while self.pages_crawled <= 500 and not self.urls.empty():
      '''
        Retrieve the next URL from the self.urls Priority Queue
        Extract the following information:
        1. Actual URL
        2. The BM25Score
        3. The Breadth first search depth
      '''
      next_url = self.urls.get()
      score = int(next_url[0])
      url = str(next_url[1][0])
      depth = int(next_url[1][1])

      print "Now Crawling: " + url
      self.depth_reached = depth

      try:
        document = self.url_controller.open(url)
        mime_type = document.info().gettype()

      # Normalise the URL before inserting
        self.visited[url] = depth

        if (mime_type in self.valid_mime_types):
          self.parse_page(document,depth,self.query)
        else:
          continue
      except IOError as e:
        print e

      self.output_file.write("Number of links crawled = " + str(self.pages_crawled))

def main():
  query = raw_input ( 'Query: ' )
  crawler = WebCrawler(query)
  crawler.crawl()


if __name__ == '__main__':
  main()

#When I wrote this, only God and I understood what I was doing
#Now, God only knows
