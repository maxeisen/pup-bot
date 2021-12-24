from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from twilio.rest import Client
from retry import retry
import tweepy
import requests
import random
import constants
import secrets

# Authenticate and initialize Tweepy instance 
def initializeTweepy():
  auth=tweepy.OAuthHandler(secrets.API_KEY, secrets.API_KEY_SECRET)
  auth.set_access_token(secrets.ACCESS_TOKEN, secrets.ACCESS_TOKEN_SECRET)
  t=tweepy.API(auth)
  return t

# Authenticate and initialize Twilio instance
def initializeTwilio():
  client=Client(secrets.TWILIO_SID, secrets.TWILIO_SECRET)
  return client

# Initialize webdriver
def initializeWebdriver():
  options=Options()
  options.add_argument('--headless')
  options.add_argument('--disable-gpu')
  s=Service(ChromeDriverManager().install())
  driver=webdriver.Chrome(service=s, options=options)
  wait=WebDriverWait(driver, 10)
  return (driver, wait)

# Pull required conversion values
@retry()
def getConversionValues(fiats=constants.FIATS, preferredFIAT=constants.PREFERRED_FIAT, publicFIAT = constants.PUBLIC_FIAT, contract=constants.CONTRACT_ADDRESS):
  driver, wait = initializeWebdriver()
  reqURL = 'https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms='+fiats
  r = requests.get(reqURL)
  ethToPrefFIAT = r.json()[preferredFIAT]
  ethToPubFIAT = r.json()[publicFIAT]
  print("1 ETH is $"+str(ethToPrefFIAT)+" "+preferredFIAT+" or $"+str(ethToPubFIAT)+" "+publicFIAT)
  uniswapURL = 'https://app.uniswap.org/#/add/ETH/'+contract+'/10000'
  driver.get(uniswapURL)
  pupPerEthElement = wait.until(EC.visibility_of_element_located((By.XPATH, "//html/body/div[1]/div/div[2]/div[4]/main/div[2]/div/div[4]/div[1]/div[2]/div[2]/span")))
  ethToPUP = float(pupPerEthElement.get_attribute("innerHTML").splitlines()[0])
  driver.quit()
  print("1 ETH is "+str(ethToPUP)+" PUP")
  return (ethToPubFIAT, ethToPrefFIAT, ethToPUP)

# Get previous value of 1000000 PUP from last Tweet
def getLastReferenceValue():
  t = initializeTweepy()
  lastTweet = t.user_timeline(user_id=secrets.BOT_ID, count=1)[0]
  lastReferencePrice = float((lastTweet.text.split('$')[2]).split(' ')[0])
  return lastReferencePrice

# Generate full price report statement
def generatePriceReport(delta, currentReferenceValue):
  priceStatement = "1 million $PUP is currently worth $"+currentReferenceValue+" "+constants.PUBLIC_FIAT+". "
  plusMinus = 'Up ' if (delta > 0) else 'Down '
  deltaStatement = plusMinus+str('{0:.2f}'.format(delta))+"% since last pupdate. "
  if (delta < -2):
    closingStatement = random.choice(constants.DIP_PHRASES)
  elif (delta > 10):
    closingStatement = random.choice(constants.HYPE_PHRASES)
  else:
    closingStatement = random.choice(constants.STABLE_PHRASES)
  priceReport = priceStatement+deltaStatement+closingStatement+" #PuppyCoin"
  return(priceReport)

# Post tweet
def postTweet(tweet):
  t = initializeTweepy()
  t.update_status(tweet)
  print("Tweeted: "+tweet)

# Send text message
def sendText(message):
  client = initializeTwilio()
  for num in secrets.RECIPIENT_NUMBERS:
    client.messages.create(body=message,from_=secrets.TWILIO_PHONE,to=num)
    print("Sent to "+num+": " + message)

# Send direct message on Twitter
def sendDirectMessage(message, recipients=secrets.RECIPIENT_IDS):
  t = initializeTweepy()
  for uid in recipients:
    t.send_direct_message(uid, message)
    print("Sent to "+uid+": " + message)

def main():
  ethToPubFIAT, ethToPrefFIAT, ethToPUP = getConversionValues()
  lastReferenceValue = getLastReferenceValue()
  currentReferenceValue = str('{0:.2f}'.format(constants.REFERENCE_AMOUNT/(ethToPUP/ethToPubFIAT)))
  delta = ((float(currentReferenceValue)-lastReferenceValue)/lastReferenceValue)*100
  priceReport = generatePriceReport(delta, currentReferenceValue)

  positionValue = str('{0:.2f}'.format(secrets.PERSONAL_HOLDINGS/(ethToPUP/ethToPrefFIAT)))
  positionReport = "Your $PUP is worth $"+positionValue+" "+constants.PREFERRED_FIAT+" before Gas fees"
  print(positionReport)

  postTweet(priceReport)
  sendDirectMessage(positionReport, recipients=[secrets.BOT_ID])
  if (delta >= secrets.ALERT_DELTA_THRESHOLD):
    personalDeltaStatement = ' - up '+str('{0:.2f}'.format(delta))+"% in the last hour!"
    sendText(positionReport+personalDeltaStatement)
    sendDirectMessage(positionReport+personalDeltaStatement)

if __name__ == "__main__":
  main()