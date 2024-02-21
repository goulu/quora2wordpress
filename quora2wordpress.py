import os
import time
import json

# This is the Quora profile page you want to scrape
page="https://fr.quora.com/profile/Philippe-Guglielmetti/answers"

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

browser = webdriver.Chrome()

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

with open(listfile, "r") as file:
    html = file.read()

print("this might take some time...", end="")
soup = BeautifulSoup(html, 'lxml')

# Find and process the questions+answers

questions = soup.findAll("div",{"class":"q-box qu-pt--medium qu-pb--medium qu-borderBottom"})
if questions is None or len(questions)==0:
    print("no questions found")
    quit()
print(len(questions),"questions found")

def formatAnswer(answer):
    paragraphs = answer.findAll("p")
    output = ""
    for p in paragraphs:
        output += "<p>"+p.text+"</p>\n"
    return output

def scrapeAnswer(page):
    browser.get(page)
    WebDriverWait(browser, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body")) 
    )
    time.sleep(0.1)
    soup = BeautifulSoup(browser.page_source, 'lxml')
    body= soup.find('body')
    title = body.find("div",{"class":"q-box qu-mb--medium qu-mt--small"})
    if title is  None: # in a Space ?
        title = body.find("div",{"class":"q-box qu-mb--tiny"})
        answer=title.next_sibling
    else:
        answer= body.findAll("span",{"class":"q-box qu-userSelect--text"})[1]

    article = {
        'title' : title.text,
        'content' : formatAnswer(answer),
        "status" : "draft"
        }
    return article

articles = []
try:
    for question in questions:
        link=question.find("a",{"class":"answer_timestamp"})['href']
        article = scrapeAnswer(link)
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
