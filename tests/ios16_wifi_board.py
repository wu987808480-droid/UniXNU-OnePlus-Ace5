"""Check power requests against the captured board's regulator constraints."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--dts',type=Path,required=True)
a=p.parse_args()
data=a.dts.read_bytes()
record=json.loads((ROOT/'hardware/sm8650-wifi.json').read_text())
# OnePlus 13R (CPH2645, same giulia board): DTS captured 2026-11-03 from /sys/firmware/fdt via dtc.
# Only the board identity is extended; the regulator and GPIO checks below still run unchanged.
ONEPLUS_13R_DTS_SHA256='be2f117af54015bb894cf1e9e5bcf2829abf28ae8f16f7f0761181fb517964a0'
assert hashlib.sha256(data).hexdigest() in (record['android_device_tree']['decoded_sha256'],ONEPLUS_13R_DTS_SHA256)
text=data.decode()
cnss=text.split('qcom,cnss-kiwi@b0000000 {',1)[1].split('};',1)[0]
wake=re.search(r'mpm_wake_set_gpios\s*=\s*<([^>]+)>;',cnss)
assert wake and [int(v,0) for v in wake[1].split()]==[18,19]
code=(ROOT/'uefi-overlay/Platforms/OnePlus/giuliaPkg/Drivers/GiuliaInitrdDxe/WifiPcie.c').read_text()
def initializer(name):
    return re.search(r'\b'+name+r'\[GW_RAILS\]=\{([^}]+)\}',code)[1]
names=re.findall(r'"([^"]+)"',initializer('mRailNames'))
volts=[int(x) for x in initializer('mMillivolts').split(',')]
limits=[int(x) for x in initializer('mMaximumMv').split(',')]
assert len(names)==len(volts)==len(limits)==9 and len(set(names))==9
for name,mv,maximum in zip(names,volts,limits):
    match=re.search(r'\brpmh-regulator-'+re.escape(name)+r'\s*\{',text)
    assert match,'Missing captured regulator '+name
    at=match.end();depth=1;end=at
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    block=text[at:end]
    low=int(re.search(r'regulator-min-microvolt\s*=\s*<(0x[0-9a-f]+)>',block)[1],16)
    high=int(re.search(r'regulator-max-microvolt\s*=\s*<(0x[0-9a-f]+)>',block)[1],16)
    assert low<=mv*1000<=maximum*1000<=high,(name,mv,maximum,low,high)
print('Wi-Fi power: all 9 requested voltages and ceilings match the pinned Ace 5 DT')
print('WLAN control routing: GPIO18/19 match the captured CNSS mpm_wake_set_gpios')
