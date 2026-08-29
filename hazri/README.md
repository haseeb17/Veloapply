# Hazri

School **chip-card / RFID attendance** for Pakistani schools. USB reader (keyboard-wedge) tap karta hai, software hazri, late, aur parent SMS queue kar deta hai.

## Demo login

- Office: `admin` / `hazri123`
- Gate kiosk: `gate` / `gate123`

```bash
cd hazri
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

Open http://127.0.0.1:8787

Hardware ke baghair demo: **Gate kiosk** page par neeche wali demo cards tap karo. Asal RFID reader bhi wahi karega — woh UID type karke Enter bhejta hai.

## Kya milta hai

- Chip card UID se student link
- Gate check-in / check-out, late after 08:15
- Daily register + CSV + monthly report
- Parent SMS log (demo mode free; live Jazz/Telenor later)
- Printable ID cards
- **Sell / cost** calculator — school ko kitne ka quote dena hai

Cost / selling price ka breakdown app ke andar **Sell / cost** page par live calculator se nikalo. Short version `COST.md` mein hai.

## Hardware (Pakistan)

Sasta USB 125kHz ya 13.56MHz Mifare reader + printable RFID cards. Reader ko gate wale laptop/tablet se USB lagaao. Kiosk page focus rakho, card tap karo.
