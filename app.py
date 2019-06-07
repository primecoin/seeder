# app.py

from flask import Flask, jsonify

import boto3
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
if 'ROUTE53_HOSTED_ZONE_ID' not in app.config:
    raise RuntimeError("Setting 'ROUTE53_HOSTED_ZONE_ID' is not configured")
if 'ROUTE53_RECORD_NAME' not in app.config:
    raise RuntimeError("Setting 'ROUTE53_RECORD_NAME' is not configured")


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

    route53 = boto3.client('route53')
    response["update"] = servers

    # Retrieve existing seeds in dns
    seedsExisting = []
    recordSet = route53.list_resource_record_sets(
        HostedZoneId=app.config['ROUTE53_HOSTED_ZONE_ID'],
        StartRecordName=app.config['ROUTE53_RECORD_NAME'],
        StartRecordType='A'
    )
    for record in recordSet["ResourceRecordSets"]:
        seedsExisting.append(record["ResourceRecords"][0]["Value"])
    response["former"] = seedsExisting

    # Add new seeds to dns
    seedsNew = []
    for server in servers:
        if server not in seedsExisting:
            seedsNew.append(server)
            route53.change_resource_record_sets(
                HostedZoneId=app.config['ROUTE53_HOSTED_ZONE_ID'],
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'CREATE',
                            'ResourceRecordSet': {
                                'Name': app.config['ROUTE53_RECORD_NAME'],
                                'Type': 'A',
                                'SetIdentifier': server,
                                'MultiValueAnswer': True,
                                'TTL': 60,
                                'ResourceRecords': [
                                    {
                                        'Value': server
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
    response["result"] = seedsExisting + seedsNew
    return jsonify(response), 200


if __name__ == '__main__':
    app.run()
