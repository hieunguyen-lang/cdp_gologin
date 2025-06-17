from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.debugger_address = "localhost:9222"

service = Service(executable_path="C:/path/to/chromedriver_135.exe")
driver = webdriver.Chrome(service=service, options=chrome_options)
