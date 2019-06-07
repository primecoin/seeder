# app.py

from flask import Flask, jsonify

import json
import re
import requests

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')
if 'NETWORK' not in app.config:
    raise RuntimeError("Setting 'NETWORK' is not configured")
if app.config['NETWORK'] != 'mainnet' and app.config['NETWORK'] != 'testnet':
    raise RuntimeError("Setting 'NETWORK' can only be 'mainnet' or 'testnet'")
if app.config['NETWORK'] == 'mainnet' and 'MAINNET_RPC_URL' not in app.config:
    raise RuntimeError("Setting 'MAINNET_RPC_URL' is not configured")
if app.config['NETWORK'] == 'testnet' and 'TESTNET_RPC_URL' not in app.config:
    raise RuntimeError("Setting 'TESTNET_RPC_URL' is not configured")


def requestJsonRPC(method, params):
    headers = {'content-type': 'application/json'}
    payload = {
        "method": method,
        "params": params,
        "jsonrpc": "1.0",
        "id": "seeder",
    }
    url = app.config['MAINNET_RPC_URL'] if app.config['NETWORK'] == 'mainnet' else app.config['TESTNET_RPC_URL']
    return requests.post(url, data=json.dumps(payload), headers=headers).json()


# API based on node JSON-RPC

@app.route('/')
def getServerIPs():
    response = requestJsonRPC("getpeerinfo", [])
    if "error" in response and response["error"] != None:
        return jsonify(response), 200
    else:
        peers = response["result"]
        servers = []
        for peer in peers:
            if peer["inbound"] == False:
                pattern = '(?P<host>(\d+\.?){4})(:?P<port>[0-9]*)?'
                match = re.search(pattern, peer["addr"])
                servers.append(match.group('host'))
    response["result"] = servers
    return jsonify(response), 200


if __name__ == '__main__':
    app.run()
