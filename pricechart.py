import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from datetime import datetime

def generatePriceChart(hour, price):
  plt.style.use('seaborn-dark')
  plt.plot(hour, price, c='silver')

  for i in range(10):
    if i == 9:
      plt.plot(hour[i], price[i], marker='*', ms=15, c='gold' )
    else:
      pointStyle = 'g^' if (price[i+1] >= price[i]) else 'rv'
      plt.plot(hour[i], price[i], pointStyle, markersize=8)

  plt.title("Puppy Coin Pupdates")
  plt.xlabel("Time (EST)")
  plt.ylabel("Price per 1 million $PUP (USD)")
  plt.xticks(hour)
  plt.grid()
  currentTimeString = datetime.now().strftime("%m%d%Y_%H%M%S")
  filename = 'pricechart_'+currentTimeString
  filepath = './pricecharts/'+filename
  plt.savefig(filepath)
  return filepath+'.png'