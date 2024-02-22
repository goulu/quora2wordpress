import os, time, re, json, requests, base64, lxml #standard libraries
from itertools import groupby

# This is the Quora profile page you want to scrape
page="https://fr.quora.com/profile/Philippe-Guglielmetti/answers"
page="https://reponsesfrequentes.quora.com/"

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

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
    no_of_pagedowns = 20
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
regex = re.compile(page+r'.+')

links = soup.findAll('a', href = regex)

links=[x.get('href') for x in links]
if links is None or len(links)==0:
    print("no post found")
    quit()
links=[key for key, _group in groupby(links)] # remove duplicates https://stackoverflow.com/a/5738933/1395973
print(len(links),"posts found")
print('\n'.join(links))

def Paragraph(p,tag="p"):
    output=p.text
    if tag:
        output = "<"+tag+">"+output+"</"+tag+">\n"
    return output

def scrapePost(page):
    browser.get(page)
    WebDriverWait(browser, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body")) 
    )
    time.sleep(0.1)
    soup = BeautifulSoup(browser.page_source, 'lxml')
    body= soup.find('body')
    root=body.find(attrs={"id":"root"})
    paragraphs= root.findAll("p")
    title = Paragraph(paragraphs[0],tag=None)
    content=''.join([Paragraph(p) for p in paragraphs[1:]])

    article = {
        'url' : page,
        'title' : title.text,
        'content' : content,
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
