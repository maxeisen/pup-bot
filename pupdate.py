import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
from twilio.rest import Client
from retry import retry
import tweepy
import requests
import random
import json
import constants
import time
from pricechart import generatePriceChart

# Load environment variables
load_dotenv()

# Authenticate and initialize Tweepy instance 
def initializeTweepy():
  auth=tweepy.OAuthHandler(os.environ.get('TWITTER_API_KEY'), os.environ.get('TWITTER_API_KEY_SECRET'))
  auth.set_access_token(os.environ.get('TWITTER_ACCESS_TOKEN'), os.environ.get('TWITTER_ACCESS_TOKEN_SECRET'))
  t=tweepy.API(auth)
  return t

# Authenticate and initialize Twilio instance
def initializeTwilio():
  client=Client(os.environ.get('TWILIO_SID'), os.environ.get('TWILIO_SECRET'))
  return client

# Initialize webdriver
def initializeWebdriver():
  options=Options()
  options.add_argument('--headless')
  options.add_argument('--disable-gpu')
  if (os.environ.get('ENVIRONMENT') == 'prod'):
    driver=webdriver.Chrome(executable_path=os.environ.get('CHROMEDRIVER_PATH'))
  else:
    s=Service(ChromeDriverManager().install())
    driver=webdriver.Chrome(service=s, options=options)
  wait=WebDriverWait(driver, 10)
  return (driver, wait)

# Pull required conversion values (retry 10 times)
@retry(tries=10, delay=5)
def getConversionValues(fiats=constants.FIATS, preferredFIAT=constants.PREFERRED_FIAT, publicFIAT = constants.PUBLIC_FIAT, contract=constants.CONTRACT_ADDRESS):
  driver, wait = initializeWebdriver()
  reqURL = 'https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms='+fiats
  r = requests.get(reqURL)
  ethToPrefFIAT = r.json()[preferredFIAT]
  ethToPubFIAT = r.json()[publicFIAT]
  print("1 ETH is $"+str(ethToPrefFIAT)+" "+preferredFIAT+" or $"+str(ethToPubFIAT)+" "+publicFIAT)
  uniswapURL = 'https://app.uniswap.org/#/add/ETH/'+contract+'/10000'
  uniswapBackupURL = 'https://app.uniswap.org/#/swap?inputCurrency=ETH&outputCurrency='+contract+'&chain=mainnet'
  ethToPUP = None
  insufficientLiquidity = False
  try:
    driver.get(uniswapURL)
    pupPerEthElement = wait.until(EC.visibility_of_element_located((By.XPATH, "//html/body/div[1]/div/div[2]/div[4]/main/div[2]/div/div[4]/div[1]/div[2]/div[2]/span")))
    ethToPUP = float(pupPerEthElement.get_attribute("innerHTML").splitlines()[0])
    currentReferenceValue = str('{0:.2f}'.format(constants.REFERENCE_AMOUNT/(ethToPUP/ethToPubFIAT)))
  except: # Backup using swap interface
    print("\nInsufficient liquidity likely. Resorting to swap interface for price retrieval.")
    insufficientLiquidity = True
    driver.quit()
    driver, wait = initializeWebdriver() # Reinitialize web driver for some reason
    driver.get(uniswapBackupURL)
    wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "ImportToken__Wrapper-sc-u4rhvt-0")))
    driver.execute_script('document.querySelector("body > reach-portal:nth-child(9) > div:nth-child(3) > div > div > div > div > div.Column__AutoColumn-sc-1r2yyln-2.bgqSvf > button").click()')
    time.sleep(2)
    pupInputElement = wait.until(EC.visibility_of_element_located((By.XPATH, "/html/body/div[1]/div/div[2]/main/div[2]/div/div[1]/div[3]/div/div[1]/input")))
    pupInputElement.send_keys(str(constants.REFERENCE_AMOUNT))
    pupToUsdElement = wait.until(EC.visibility_of_element_located((By.XPATH, "/html/body/div[1]/div/div[2]/main/div[2]/div/div[1]/div[1]/div/div[2]/div/div[1]/div/span")))
    currentReferenceValue = str('{0:.2f}'.format(float(pupToUsdElement.get_attribute("innerHTML").splitlines()[0])))
  driver.quit()
  print("1 million PUP is worth $"+currentReferenceValue+" USD")
  return (currentReferenceValue, ethToPUP, ethToPrefFIAT, insufficientLiquidity)

# Get previous value of 1000000 PUP from last Tweet
def getPreviousPrices():
  t = initializeTweepy()
  prices = []
  hours = []
  previousPupdates = t.user_timeline(user_id=os.environ.get('TWITTER_BOT_ID'), count=constants.NUM_PREVIOUS_PUPDATES-1)
  lastPupdate = previousPupdates[0]
  for i in reversed(previousPupdates):
    prices.append(float((i.text.split('$')[2]).split(' ')[0]))
    tweetTime = i.created_at
    tweetTimeIndex = int(tweetTime.hour)
    hours.append(constants.UTC_CLOCK_TIMES[tweetTimeIndex])
  lastReferencePrice = float((lastPupdate.text.split('$')[2]).split(' ')[0])
  return lastReferencePrice, hours, prices

# Generate full price report statement
def generatePriceReport(delta, currentReferenceValue):
  priceStatement = "1 million $PUP is currently worth $"+currentReferenceValue+" "+constants.PUBLIC_FIAT+". "
  plusMinus = 'Up ' if (delta > 0) else 'Down '
  deltaStatement = plusMinus+str('{0:.2f}'.format(abs(delta)))+"% since last pupdate. "
  if (delta < constants.DELTA_DIP_THRESHOLD):
    closingStatement = random.choice(constants.DIP_PHRASES)
  elif (delta > constants.DELTA_RALLY_THRESHOLD):
    closingStatement = random.choice(constants.RALLY_PHRASES)
  else:
    closingStatement = random.choice(constants.STABLE_PHRASES)
  priceReport = priceStatement+deltaStatement+closingStatement+" #PuppyCoin"
  return(priceReport)

# Generate position reports
def generateAndSendPositionReports(delta, positions, currentReferenceValue, ethToPUP, ethToPrefFIAT, massSend):
  if massSend:
    for holder, position in positions.items():
      positionValue = str('{0:.2f}'.format(int(position)/(ethToPUP/ethToPrefFIAT))) if ethToPUP else str('{0:.2f}'.format((currentReferenceValue*(int(position)/constants.REFERENCE_AMOUNT))))
      positionReport = "Your $PUP is now worth $"+positionValue+" "+constants.PREFERRED_FIAT+" before fees"
      personalDeltaStatement = 'PUPDATE: '+str('{0:.2f}'.format(delta))+"% change in the last hour! "
      finalPositionReport = personalDeltaStatement+positionReport
      sendText(finalPositionReport, holder)
  else:
    positionValue = str('{0:.2f}'.format(int(positions[os.environ.get('PERSONAL_NUMBER')])/(ethToPUP/ethToPrefFIAT))) if ethToPUP else str('{0:.2f}'.format((currentReferenceValue*(int(positions[os.environ.get('PERSONAL_NUMBER')])/constants.REFERENCE_AMOUNT))))
    positionReport = "Your $PUP is now worth $"+positionValue+" "+constants.PREFERRED_FIAT+" before fees"
    personalDeltaStatement = 'PUPDATE: '+str('{0:.2f}'.format(delta))+"% change in the last hour! "
    finalPositionReport = personalDeltaStatement+positionReport
    return finalPositionReport

# Post tweet
def postTweet(tweet, image=None):
  t = initializeTweepy()
  if image:
    t.update_status_with_media(status=tweet, filename=image)
    print("Tweeted with price chart: "+tweet)
  else:
    t.update_status(tweet)
    print("Tweeted: "+tweet)

# Send text message
def sendText(message, recipient=os.environ.get('PERSONAL_NUMBER')):
  client = initializeTwilio()
  client.messages.create(body=message,from_=os.environ.get('TWILIO_PHONE'),to=recipient)
  print("Sent to "+recipient+": " + message)

# Send direct message on Twitter
def sendDirectMessage(message, recipients=(os.environ.get('TWITTER_RECIPIENT_IDS')).split(',')):
  t = initializeTweepy()
  for uid in recipients:
    t.send_direct_message(uid, message)
    print("Sent to "+uid+": " + message)

def main():
  currentReferenceValue, ethToPUP, ethToPrefFIAT, insufficientLiquidity = getConversionValues()
  lastReferenceValue, hours, prices = getPreviousPrices()
  prices.append(float(currentReferenceValue))
  currentHour = constants.EST_CLOCK_TIMES[int(datetime.now().strftime("%H"))] if (os.environ.get('ENVIRONMENT') == 'dev') else constants.UTC_CLOCK_TIMES[int(datetime.now().strftime("%H"))]
  hours.append(currentHour)
  delta = ((float(currentReferenceValue)-lastReferenceValue)/lastReferenceValue)*100
  
  priceChart = generatePriceChart(hours, prices, delta)
  priceReport = generatePriceReport(delta, currentReferenceValue)

  if (os.environ.get('ENVIRONMENT') == 'prod'):
    postTweet(priceReport, image=priceChart) # !!! Post to @PuppyCoinBot

  personalPositionReport = generateAndSendPositionReports(delta, json.loads(os.environ.get('PERSONAL_HOLDINGS')), float(currentReferenceValue), ethToPUP, ethToPrefFIAT, False)
  print(personalPositionReport)
  sendDirectMessage(personalPositionReport, recipients=[os.environ.get('TWITTER_BOT_ID')]) # Send to @PuppyCoinBot

  if ((delta >= int(os.environ.get('DELTA_ALERT_UPPER_THRESHOLD'))) or (delta <= int(os.environ.get('DELTA_ALERT_LOWER_THRESHOLD')))):
    generateAndSendPositionReports(delta, json.loads(os.environ.get('PERSONAL_HOLDINGS')), float(currentReferenceValue), ethToPUP, ethToPrefFIAT, True)
    sendDirectMessage(personalPositionReport)

  if (insufficientLiquidity):
    sendDirectMessage("Insufficient ETH liquidity.", recipients=["23239605"]) # Send to @MaxEisen

if __name__ == "__main__":
  main()