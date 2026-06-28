import requests
import json

url = "https://www.daegu.go.kr/daeguchain/v2/mitum/token/create"
headers = {
    "Content-Type": "application/json"
}
data = {
    "token": "234f2b655e789914a7574f607f0f9ebd",
    "chain": "dchain",
    "owner_addr": "0x65e00aBd9782cf12839acd07B7D13f7E23D08432fca",
    "owner_pkey": "59c191aba12df1ce59cae76c1c22399fa25e43350880f9595d9bf55e23b3f9cafpr",
    "token_name": "ESSENTIAL_VIDEO_1",
    "token_symbol": "TT1",
    "decimals": 9,
    "supply": 100
}

response = requests.post(url, headers=headers, data=json.dumps(data))

if response.status_code == 200:
    print(f"Status Code: {response.status_code}")
    res_json = response.json()
    print(res_json)
    with open('create_token_reponse_body.json', 'w') as j:
        json.dump(res_json, j, indent=2)
else:
    print(response.status_code)
    print(response.json())