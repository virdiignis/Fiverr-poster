from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import DesiredCapabilities
from random import choice
from time import sleep, strftime
from multiprocessing import Process, Queue
from bs4 import BeautifulSoup
from string import ascii_lowercase as letters
import re
from conf import *


def log(string):
    with open('scraper.log', 'a') as LOG:
        LOG.write(str(strftime('%H:%M:%S ')) + string + '\n')
        print(str(strftime('%H:%M:%S ')) + string)


def run():
    with open(message_path) as fp:
        message = [line.strip() for line in fp.readlines()][0]
    with open(target_urls_path)as fp:
        target_urls = [line.strip() for line in fp.readlines()]
    with open(used_logins_path)as fp:
        used = (line.strip() for line in fp.readlines())

    gigs_queue = Queue()
    driver = [start_driver()]
    for url in target_urls:
        gigs = get_gigs(driver, url)
        for gig in gigs:
            if gig[0] not in used:
                gigs_queue.put(gig)
    driver[0].quit()

    processes = []
    for _ in range(processes_count):
        processes.append(Process(target=perform, args=(gigs_queue, message)))
    for p in processes:
        p.start()
        sleep(3)
    for p in processes:
        p.join()


def perform(gigs, message):
    driver = [start_driver()]
    send_messages(driver, gigs, message)
    driver[0].quit()


def start_driver():
    with open(proxies_path) as fp:
        proxies = [line.strip() for line in fp.readlines()]
    proxy = choice(proxies)
    if CHROME:
        opts = webdriver.ChromeOptions()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--proxy-server=%s" % proxy)
        driver = [webdriver.Chrome(chrome_options=opts)]
        mail = webdriver.Chrome(chrome_options=opts)
    else:
        service_args = [
            '--proxy=w%s' % proxy,
            '--proxy-type=http',
        ]
        dcap = dict(DesiredCapabilities.PHANTOMJS)
        dcap["phantomjs.cli.args"] = service_args
        driver = [webdriver.PhantomJS(desired_capabilities=dcap, service_args=service_args)]
        mail = webdriver.PhantomJS(desired_capabilities=dcap, service_args=service_args)
        driver[0].set_window_size(1920, 1060)

    mail.get("https://dropmail.me")
    email = WebDriverWait(mail, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".email"))).text
    email = "%s@%s.%s" % (email.split('@')[0], ''.join((choice(letters) for i in range(4))), email.split('@')[1])
    driver[0].get("https://www.fiverr.com/join")
    driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
    input_element = WebDriverWait(driver[0], 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, '.js-form-email')))
    input_element.send_keys(email)
    input_element.send_keys(Keys.ENTER)
    name = email.split("@")[0]
    WebDriverWait(driver[0], 10).until(EC.visibility_of_element_located((By.CLASS_NAME, 'js-form-username'))).send_keys(
        name)
    WebDriverWait(driver[0], 10).until(EC.visibility_of_element_located((By.CLASS_NAME, 'js-form-password'))).send_keys(
        password)
    sleep(2)
    driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
    WebDriverWait(driver[0], 10).until(EC.visibility_of_element_located((By.ID, 'join-btn'))).click()
    driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
    WebDriverWait(driver[0], 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".desktop")))
    driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
    WebDriverWait(mail, 540).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".mail-subject")))
    sleep(1)
    link = BeautifulSoup(mail.page_source, "lxml").find("a", {
        "href": re.compile("http://www.fiverr.com/linker*")})["href"]
    driver[0].get(link)
    sleep(1)
    with open('configurations/accounts.txt', 'a') as file:
        file.write(email + ':' + password + '\n')
    mail.quit()
    return driver[0]


def get_gigs(driver, url):
    driver[0].get(url)
    driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
    wait = WebDriverWait(driver[0], 10)
    gigs = []
    link = ''
    while True:
        try:
            driver[0].execute_script("window.scrollTo(0, document.body.scrollHeight);")
            driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".js-gig-card")))
            items = BeautifulSoup(driver[0].page_source).find_all("div", {"class": "js-gig-card"})
            for item in items:
                gig_id = item['data-gig-id']
                freelancer_name = item['data-gig-seller-name']
                gigs.append((freelancer_name, gig_id))
        except TimeoutException:
            driver[0].quit()
            driver[0] = start_driver()
            driver[0].get(link)
            wait = WebDriverWait(driver[0], 10)
            continue
        try:
            sleep(sleep_time_gigs)
            link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".js-next"))).get_attribute("href")
            driver[0].get(link)
        except StaleElementReferenceException:
            sleep(3)
            try:
                link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".js-next"))).get_attribute("href")
                driver[0].get(link)
            except TimeoutException:
                break
        except TimeoutException:
            break  # last page
    return gigs


def send_messages(driver, gigs, message):
    wait = WebDriverWait(driver[0], 10)
    i = 1
    while not gigs.empty():
        gig = gigs.get()
        driver[0].get('https://www.fiverr.com/conversations/%s?related_gig_id=%s' % gig)
        driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
        try:
            text_area = wait.until(EC.visibility_of_element_located((By.ID, 'message_body')))
        except TimeoutException:
            gigs.put(gig)
            driver[0].quit()
            driver[0] = start_driver()
            wait = WebDriverWait(driver[0], 10)
            continue
        formatted_message = message.replace('{{ USERNAME }}', gig[0]).split('{{ NEWLINE }}')
        for x in formatted_message:
            text_area.send_keys(x)
            text_area.send_keys(Keys.ENTER)
        driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
        try:
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".btn-send-message"))).click()
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".msg-body p")))
            driver[0].save_screenshot(strftime('screenshots/%H_%M_%S.png'))
        except TimeoutException:
            gigs.put(gig)
            driver[0].quit()
            driver[0] = start_driver()
            wait = WebDriverWait(driver[0], 10)
            continue
        log('Message sent to: %s\tNr:%i' % (gig[0], i))
        i += 1
        with open(used_logins_path, "a") as fp:
            fp.write(gig[0] + '\n')
        sleep(sleep_time)


if __name__ == "__main__":
    run()
