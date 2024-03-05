import re

# This is the Quora profile page you want to scrape
page="https://fr.quora.com/profile/Philippe-Guglielmetti/answers"
regex = re.compile('https://fr.quora.com/.*/answer/Philippe-Guglielmetti')

# if you want to scrape a Space, uncomment the following 2 lines
# page="https://reponsesfrequentes.quora.com/"
# regex = re.compile(page+r'.+')

reference2wiki=True # true if yuour WP uses https://wordpress.org/plugins/reference-2-wiki/

import os, time, json, requests, base64, lxml #standard libraries
from itertools import groupby

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup, NavigableString

options = webdriver.ChromeOptions()
options.add_experimental_option('excludeSwitches', ['enable-logging'])
browser = webdriver.Chrome(options=options)

# This is the file where the scraped HTML will be saved
# If the file exists, the script will use it instead of scraping the page again
listfile="list.html"

def scrapelist(page):

    browser.get(page)
    time.sleep(1)
    elem = browser.find_element(By.TAG_NAME,"body")
    no_of_pagedowns = 2
    while no_of_pagedowns:
        elem.send_keys(Keys.PAGE_DOWN)
        time.sleep(0.5)
        no_of_pagedowns-=1
    with open(listfile, "w",encoding='utf-8') as file:
        file.write(browser.page_source)

if not os.path.isfile(listfile) :
    print("scraping",page,"to",listfile)
    scrapelist(page)

with open(listfile, "r", encoding="utf8", errors="surrogateescape") as file:
    html = file.read()

print("this might take some time...", end="")
soup = BeautifulSoup(html, 'lxml')

# Find links to all  posts

links = soup.findAll('a', href = regex)

links=[x.get('href') for x in links]
if links is None or len(links)==0:
    print("no post found")
    quit()
links=[key for key, _group in groupby(links)] # remove duplicates https://stackoverflow.com/a/5738933/1395973
print(len(links),"posts found")

rewikipedia=[re.compile(r"https:\/\/(.*).wikipedia.org\/wiki\/(.*)"),
             re.compile(r"https:\/\/(.*).wikipedia.org\/w\/index.php\?title=(.*)&a")]

def Recurse(element,notag=False):
    if isinstance(element,NavigableString): 
        return element.text # no children
    tag=element.name
    # process some tags
    if tag=='a':
        href=element.get('href')
        text=''.join(element.findAll(text=True, recursive=False))
        if reference2wiki:
            for regex in rewikipedia:
                m=re.match(regex,href)
                if m:
                    groups=list(m.groups())
                    groups.append(text)
                    return '[['+'|'.join(groups)+']]'
        return '<a href="'+href+'">'+text+'</a>'
    if tag=='img':
        #TODO : upoad the image to wordpress
        return '<img src="'+element.get('src')+'"/>'
    if tag=='svg' : # ignore svg
        return ''
    if tag=='div': 
        tag=None #ignore
    if tag=='span':
        # add bold/italic detection one day, in this case we will keep the span
        tag=None #ignore because spans are inline blocks in Quora

    content= ''.join([Recurse(child) for child in element.children])
    if not notag and tag and content:
        content = "<"+tag+">"+content+"</"+tag+">"
    return content

def scrapePost(page):
    browser.get(page)
    browser.find_element(By.TAG_NAME,"body")
    soup = BeautifulSoup(browser.page_source, 'lxml')
    body= soup.find('body')
    root=body.find(attrs={"id":"mainContent"})
    try:
        root=root.select_one('div:first-child')
        root=root.select_one('div:first-child')
        root=root.select_one('div:first-child')
        span=root.find('span',{'class':'qu-userSelect--text'})
        children=list(span.children)
        if len(children)>1: # it is a space
            title=children.pop(0).text
            content= ''.join([Recurse(child) for child in children])
        else: # it is an answer
            children=list(root.children)
            title=children[0].text
            content=Recurse(children[2],True)
        # now get the date on the log page
        browser.get(page+"/log")
        browser.find_element(By.TAG_NAME,"body")
        log = BeautifulSoup(browser.page_source, 'lxml')
        text=log.text
        redatetime=re.compile(r"([0-9]{1,2}) (\S*) ([0-9]{4}) à ([0-9]{1,2}):([0-9]{1,2}):([0-9]{1,2})") # french version
        dates=list(re.findall(redatetime,text))
        date=dates[-1]
        month=date[1].replace("janvier","01").replace("février","02").replace("mars","03").replace("avril","04").replace("mai","05").replace("juin","06").replace("juillet","07").replace("août","08").replace("septembre","09").replace("octobre","10").replace("novembre","11").replace("décembre","12")
        date=f'{date[0]}:{month}:{date[2]}T{date[3]}:{date[4]}:{date[5]}' #in WP format YYYY-MM-DDTHH:MM:SS according to https://core.trac.wordpress.org/ticket/41032

    except:
        raise Exception("unknown page type")

    article = {
        'url' : page,
        'title' : title,
        'content' : content,
        'date' : date,
        "status" : "draft"
        }
    return article

articles = []
try:
    for link in links:
        print("scraping",link,end='...')
        article = scrapePost(link)
        print(article['title'])
        articles.append(article)
finally:
    with open("output.json", "w") as outfile:
        json.dump(articles, outfile)

quit()

import requests
import base64


import lxml # https://thehftguy.com/2020/07/28/making-beautifulsoup-parsing-10-times-faster/



username = "your username"
password = "see readme.md and paste your password here"

creds = username + ':' + password
cred_token = base64.b64encode(creds.encode())

header = {'Authorization': 'Basic ' + cred_token.decode('utf-8')}

api = "http://localhost/wordpress/wp-json/wp/v2"

# Read the HTML file
with open("Quora 1.html", "r") as file:
    html = file.read()

print("this might take some time...", end="")
soup = BeautifulSoup(html, 'lxml')

print("done !")

# Create a new post on WordPress
# https://developer.wordpress.org/rest-api/reference/posts/
article = {
 'title' : 'This is WordPress Python Integration Testing',

 'content' : 'Hello, this content is published using WordPress Python Integration',
 'status' : 'publish', 
 'categories': 5, 
 'date' : '2021-12-05T11:00:00'
}

response = requests.post(api+"/posts", json=article, headers=header)

# Check the response status
if response.status_code == 201:
    print("Post published successfully!")
else:
    print("Failed to publish the post. Error:", response.text)
