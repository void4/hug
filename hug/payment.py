"""hug/payment.py

Provides the basic built-in payment helper functions

Copyright (C) 2016  Arndt Schnabel

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

"""
from __future__ import absolute_import

import base64
import binascii
import json
import six
import base64

from falcon import HTTPError, HTTP_402, HTTPUnauthorized

from web3 import Web3, IPCProvider
from hug.store import PersistentStore

class HTTPPaymentRequired(HTTPError):

    def __init__(self, title, description, **kwargs):
        super(HTTPPaymentRequired, self).__init__(HTTP_402, title, description, **kwargs)


pstore = PersistentStore()

web3 = Web3(IPCProvider(testnet=True))
web3.config.defaultAccount = "0x3b63b366a72e5742B2aaa13a5e86725ED06a68f3"

contract_address = "0x1EEcb87dE18ac28c1824d9274f2cEBC5442F8c57"

abi = """[ { "constant": true, "inputs": [ { "name": "channel", "type": "uint256" }, { "name": "value", "type": "uint256" } ], "name": "getHash", "outputs": [ { "name": "", "type": "bytes32", "value": "0x1c44b375153723d5b41d6a7350691ea6f95b8a08e93f90b8c6d1f3ee6552bbba", "displayName": "" } ], "type": "function" }, { "constant": false, "inputs": [ { "name": "channel", "type": "uint256" } ], "name": "reclaim", "outputs": [], "type": "function" }, { "constant": true, "inputs": [ { "name": "channel", "type": "uint256" }, { "name": "value", "type": "uint256" }, { "name": "v", "type": "uint8" }, { "name": "r", "type": "bytes32" }, { "name": "s", "type": "bytes32" } ], "name": "verify", "outputs": [ { "name": "", "type": "bool", "value": false, "displayName": "" } ], "type": "function" }, { "constant": true, "inputs": [], "name": "channelCount", "outputs": [ { "name": "", "type": "uint256", "value": "0", "displayName": "" } ], "type": "function" }, { "constant": false, "inputs": [ { "name": "channel", "type": "uint256" } ], "name": "deposit", "outputs": [], "type": "function" }, { "constant": true, "inputs": [ { "name": "channel", "type": "uint256" } ], "name": "isValidChannel", "outputs": [ { "name": "", "type": "bool", "value": false, "displayName": "" } ], "type": "function" }, { "constant": false, "inputs": [ { "name": "receiver", "type": "address" }, { "name": "expiry", "type": "uint256" } ], "name": "createChannel", "outputs": [ { "name": "channel", "type": "uint256" } ], "type": "function" }, { "constant": true, "inputs": [ { "name": "", "type": "uint256" } ], "name": "channels", "outputs": [ { "name": "sender", "type": "address", "value": "0x", "displayName": "sender" }, { "name": "receiver", "type": "address", "value": "0x", "displayName": "receiver" }, { "name": "value", "type": "uint256", "value": "0", "displayName": "value" }, { "name": "expiry", "type": "uint256", "value": "0", "displayName": "expiry" }, { "name": "valid", "type": "bool", "value": false, "displayName": "valid" } ], "type": "function" }, { "constant": false, "inputs": [ { "name": "channel", "type": "uint256" }, { "name": "value", "type": "uint256" }, { "name": "v", "type": "uint8" }, { "name": "r", "type": "bytes32" }, { "name": "s", "type": "bytes32" } ], "name": "claim", "outputs": [], "type": "function" }, { "anonymous": false, "inputs": [ { "indexed": true, "name": "sender", "type": "address" }, { "indexed": true, "name": "receiver", "type": "address" }, { "indexed": false, "name": "channel", "type": "uint256" } ], "name": "NewChannel", "type": "event" }, { "anonymous": false, "inputs": [ { "indexed": true, "name": "sender", "type": "address" }, { "indexed": true, "name": "receiver", "type": "address" }, { "indexed": false, "name": "channel", "type": "uint256" } ], "name": "Deposit", "type": "event" }, { "anonymous": false, "inputs": [ { "indexed": true, "name": "who", "type": "address" }, { "indexed": true, "name": "channel", "type": "uint256" } ], "name": "Claim", "type": "event" }, { "anonymous": false, "inputs": [ { "indexed": true, "name": "channel", "type": "bytes32" } ], "name": "Reclaim", "type": "event" } ]"""

contract = web3.eth.contract(abi).at(contract_address)

def authenticator(function):
    def accountwrapper(account):
        def wrapper(amount):
            payuri = "pay://{0}/{1}".format(account, toWei(amount))
            function.__doc__ = payuri
            def authenticate(request, response, **kwargs):
                result = function(request, response, account, amount, **kwargs)
                if result is None:
                    #raise HTTPUnauthorized('Payment Required',
                    #                       'Please provide valid {0} signatures'.format(function.__doc__.splitlines()[0]))
                    raise HTTPPaymentRequired("Payment Required", payuri)

                if result is False:
                    raise HTTPUnauthorized('Invalid Payment',
                                           'Provided {0} signatures were invalid'.format(function.__doc__.splitlines()[0]))

                request.context['payment'] = result
                return True

            authenticate.__doc__ = function.__doc__
            return authenticate

        return wrapper
    return accountwrapper

def toWei(amount):
    if isinstance(amount, str):
        split = amount.split(" ")
        try:
            if len(split) == 1:
                    return int(amount)
            elif len(split) == 2:
                return int(web3.toWei(split[0], split[1]))
            else:
                print("Server side error: invalid amount")
                return None
        except ValueError:
                return None
    elif isinstance(amount, int):
        return amount

@authenticator
def channel(request, response, account, amount, **kwargs):
    """Payment verification

    Checks if a signed payment channel header was included and is valid.
    In this case, verify_user supplies the minimum value of the transaction.
    The target address is the coinbase of the Ethereum client.
    """

    amount = toWei(amount)
    if amount is None:
        raise ValueError("Invalid amount")

    header = request.get_header("X-Signature")
    if header is None:
        return None

    header = base64.b64decode(header)

    if six.PY3:
        header = header.decode("utf8")

    header = json.loads(header)

    print(json.dumps(header, sort_keys=True, indent=4, separators=(',', ': ')))

    existing = pstore.getn(header["channel"])
    if existing is None:
        existing = {"value": 0}

    receiver = contract.channels(header["channel"])[1]#should be dict?
    
    if receiver != account:
        raise HTTPUnauthorized("Invalid Payment", "Payment channel target {0} should be {1}.".format(receiver, account))

    if header["value"]-existing["value"]<amount:
        raise HTTPUnauthorized("Invalid Payment", "Payment channel value increment +{0} too small. Expected +{1} to {2}.".format(header["value"]-existing["value"], amount, existing["value"]+amount))

    if header["value"]-existing["value"]>amount:
        raise HTTPUnauthorized("Invalid Payment", "Payment channel value increment +{0} too large. Expected +{1} to {2}.".format(header["value"]-existing["value"], amount, existing["value"]+amount))


    # Also check if payment channel closes soon

    if contract.verify(header["channel"], header["value"], header["signature"]["v"], header["signature"]["r"], header["signature"]["s"]):
        
        pstore.set(header["channel"], header)#should set contractid:channelid
        print(account, amount, existing)
        return amount

    else:
        raise HTTPUnauthorized("Invalid Payment", "Signature invalid.")

