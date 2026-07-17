import csv
import json
import random
import uuid
from datetime import datetime, timedelta

NUM_REGISTROS_PLAYERS = 600
NUM_REGISTROS_SESSIONS = 4000
NUM_REGISTROS_TRANS = 1800
NUM_REGISTROS_AFI = 2000

cidades = [
"São Paulo","Rio de Janeiro","Curitiba",
"Belo Horizonte","Porto Alegre","Salvador"
]

devices = ["android","ios","desktop"]

countries = ["BR","MX","AR","CL","CO"]

transaction_types = ["deposit","withdraw","bet"]

players = []

print("Gerando players...")

for i in range(NUM_REGISTROS_PLAYERS):

    player = {
        "player_id": f"pl_{1000+i}",
        "email": f"user{i}@mail.com" if random.random() > 0.2 else f"USER{i}@MAIL.COM",
        "city": random.choice(cidades),
        "created_at": (datetime.now() - timedelta(days=random.randint(1,900))).strftime("%Y-%m-%d")
    }

    players.append(player)

with open("players.json","w",encoding="utf8") as f:
    json.dump(players,f,indent=2,ensure_ascii=False)

print("players.json criado")



print("Gerando sessions...")

sessions = []

for i in range(NUM_REGISTROS_SESSIONS):

    sessions.append({
        "session_id": f"ss_{2000+i}",
        "player_id": random.choice(players)["player_id"],
        "ip": f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
        "device": random.choice(devices),
        "timestamp": (datetime.now() - timedelta(minutes=random.randint(1,100000))).isoformat()
    })

with open("sessions.json","w",encoding="utf8") as f:
    json.dump(sessions,f,indent=2)

print("sessions.json criado")



print("Gerando transactions...")

with open("transactions.csv","w",newline="",encoding="utf8") as f:

    writer = csv.writer(f)

    writer.writerow([
        "transaction_id",
        "player_id",
        "type",
        "amount",
        "timestamp"
    ])

    for i in range(NUM_REGISTROS_TRANS):

        writer.writerow([
            f"tx_{3000+i}",
            random.choice(players)["player_id"],
            random.choice(transaction_types),
            round(random.uniform(10,3000),2),
            (datetime.now() - timedelta(days=random.randint(0,365))).strftime("%Y-%m-%d %H:%M:%S")
        ])

print("transactions.csv criado")



print("Gerando affiliate_cpa_ftd...")

with open("affiliate_cpa_ftd.csv","w",newline="",encoding="utf8") as f:

    writer = csv.writer(f)

    writer.writerow([
        "affiliate_id",
        "player_id",
        "country",
        "clicks",
        "registrations",
        "ftd",
        "cpa_value"
    ])

    for i in range(NUM_REGISTROS_AFI):

        clicks = random.randint(1,200)
        regs = random.randint(0,30)
        ftd = random.randint(0,10)

        writer.writerow([
            f"aff_{random.randint(1,50)}",
            random.choice(players)["player_id"],
            random.choice(countries),
            clicks,
            regs,
            ftd,
            random.choice([30,40,50,60,75,100])
        ])

print("affiliate_cpa_ftd.csv criado")

print("Arquivos gerados com sucesso!")