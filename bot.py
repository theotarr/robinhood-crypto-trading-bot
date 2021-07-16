import time
import threading
import talib
import pandas as pd
import numpy as np
import robin_stocks.robinhood as rh
import email
import smtplib
import ssl
import os
from binance.client import Client
from provider import PROVIDERS
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# env file, binance api
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

client = Client(os.getenv('API_KEY'), os.getenv('API_SECRET'))

# data params
pair = 'ETHUSDT'
candles = '1d'
period = '26 days ago EST'

# robinhood params
crypto = 'ETH'
quantity = 0.05


class Data:
    def getData(pair, candles, period):

        try:
            frame = pd.DataFrame(
                client.get_historical_klines(pair, candles, period))
            frame = frame.astype(float)
        except:
            print('No data was fetched.')

        RSIperiod = 14
        SMAperiod = 9
        BOLperiod = 20

        global lastprice
        price = client.get_symbol_ticker(symbol=pair)
        lastprice = price['price']
        lastprice = float(lastprice)
        lastprice = round(lastprice, 2)

        Data.SMA(frame, SMAperiod)
        Data.RSI(frame, RSIperiod)
        Data.BOL(frame, BOLperiod)
        Data.displayData()
        eval()

    def SMA(data, period):

        global sma
        sma = 0
        dataArr = np.array(data)
        closes = dataArr[:, 3]
        close = closes.astype(float)

        for i in range(period):
            sma += close[i]
        sma = sma / period

        sma = round(sma, 2)

    def RSI(data, period):

        global rsi

        dataArr = np.array(data)
        closes = dataArr[:, 3]
        close = closes.astype(float)
        close[len(close)-1] = lastprice

        rsi = talib.RSI(close, period)
        rsi = rsi[len(rsi)-1]
        rsi = round(rsi, 2)

    def BOL(data, period):

        global upperband, middleband, lowerband

        dataArr = np.array(data)
        closes = dataArr[:, 3]
        close = closes.astype(float)
        close[len(close)-1] = lastprice

        upperband, middleband, lowerband = talib.BBANDS(close, period)
        upperband = upperband[len(upperband) - 1]
        lowerband = lowerband[len(lowerband) - 1]
        middleband = middleband[len(middleband) - 1]

        upperband = round(upperband, 2)
        middleband = round(middleband, 2)
        lowerband = round(lowerband, 2)

    def displayData():
        data = [{'Pair': pair, 'Price': lastprice, 'SMA': sma, 'RSI': rsi,
                'BOLU': upperband, 'MA': middleband, 'BOLD': lowerband}]

        display = pd.DataFrame(data)
        display = display.iloc[:, :7]
        display = display.set_index('Pair')
        print(display)


def login(days):
    time_logged_in = 60*60*24*days
    rh.authentication.login(os.getenv('RH_USERNAME'), os.getenv(
        'RH_PASSWORD'), expiresIn=time_logged_in, scope='internal', by_sms=True, store_session=True, mfa_code=None)


def logout():
    rh.authentication.logout()


def eval():
    if rsi <= 40 and lastprice < (middleband):
        buy()


def buy():
    try:
        order = rh.orders.order_buy_crypto_by_quantity(
            crypto, quantity, timeInForce='gtc', jsonify=True)
        buy_price = lastprice
        stop_loss = buy_price * 0.96
        take_profit = buy_price * 1.04
        rh.orders.order_sell_crypto_limit(
            crypto, quantity, take_profit, timeInForce='gtc', jsonify=True)
        message = f"Bought {quantity} {crypto}, Stop-Loss {stop_loss}, Take-Profit {take_profit}"
        SMS(message)

    except:
        print('Error Placing Order')

    # set limit order

    print(buy_price, stop_loss, take_profit)

    inTrade = True

    while inTrade is True:
        if lastprice <= stop_loss:
            rh.order_sell_crypto_by_quantity(
                crypto, quantity, timeInForce='gtc', jsonify=True)
            inTrade = False
            message = "Stopped Out"
            SMS(message)

        if lastprice >= take_profit:
            message = "Took Profit"
            inTrade = False
            SMS(message)

        time.sleep(5)


def format_provider_email_address(number: str, provider: str, mms=False):
    provider_info = PROVIDERS.get(provider)
    domain = provider_info.get("sms")
    return f"{number}@{domain}"


def send_sms_via_email(number: str, message: str, provider: str, sender_credentials: tuple, subject: str = "Trading Bot", smtp_server: str = "smtp.gmail.com", smtp_port: int = 465,):
    sender_email, email_password = sender_credentials
    receiver_email = format_provider_email_address(number, provider)

    email_message = f"To:{receiver_email}\n{message}"

    with smtplib.SMTP_SSL(
        smtp_server, smtp_port, context=ssl.create_default_context()
    ) as email:
        email.login(sender_email, email_password)
        email.sendmail(sender_email, receiver_email, email_message)


def SMS(message):
    number = os.getenv('PHONE_NUMBER')
    message = message
    provider = os.getenv('INTERNET_PROVIDER')
    sender_credentials = (os.getenv('EMAIL'), os.getenv('EMAIL_PASSWORD'))
    send_sms_via_email(number, message, provider, sender_credentials)


def setInterval(time):
    e = threading.Event()
    while not e.wait(time):
        Data.getData(pair, candles, period)


if __name__ == "__main__":
    login(days=1)
    Data.getData(pair, candles, period)
    setInterval(20)
