import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from datetime import datetime

def generatePriceChart(hours, prices):
  plt.style.use('seaborn-dark')
  plt.plot(hours, prices, c='silver')

  for i in range(10):
    if i == 9:
      plt.plot(hours[i], prices[i], marker='*', ms=15, c='gold' )
    else:
      pointStyle = 'g^' if (prices[i+1] >= prices[i]) else 'rv'
      plt.plot(hours[i], prices[i], pointStyle, markersize=8)

  plt.title("Puppy Coin Pupdates")
  plt.xlabel("Time (EST)")
  plt.ylabel("Price per 1 million $PUP (USD)")
  plt.xticks(hours)
  plt.grid()
  currentTimeString = datetime.now().strftime("%m%d%Y_%H%M%S")
  filename = 'pricechart_'+currentTimeString
  filepath = './pricecharts/'+filename
  plt.savefig(filepath)
  return filepath+'.png'