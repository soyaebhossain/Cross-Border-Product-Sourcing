"""
Seeds 6 new categories of products that are scarce in Bangladesh
but can be imported from China, Singapore, Thailand, Japan, or Germany.
Safe to re-run — skips existing slugs.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from catalog.models import Category, Product, ProductVariant

NEW_CATEGORIES = [
    {"name": "Industrial Automation", "slug": "industrial-automation"},
    {"name": "Medical Equipment",     "slug": "medical-equipment"},
    {"name": "Agricultural Tech",     "slug": "agricultural-tech"},
    {"name": "Clean Energy & EV",     "slug": "clean-energy-ev"},
    {"name": "Scientific Instruments","slug": "scientific-instruments"},
    {"name": "3D Printing & Maker",   "slug": "3d-printing-maker"},
]

PRODUCTS = {
    "industrial-automation": [
        {"name":"Siemens S7-1200 PLC CPU 1214C","model":"6ES7214-1AG40-0XB0","img":"plc","v":[{"n":"24VDC 100kB","w":0.44,"l":11.0,"wi":10.0,"h":7.5}]},
        {"name":"Mitsubishi MELSEC FX5U-32MT PLC","model":"FX5U-32MT/ES","img":"plc","v":[{"n":"AC Power 32 I/O","w":0.62,"l":15.0,"wi":9.5,"h":8.7}]},
        {"name":"Delta DVP32ES2 PLC","model":"DVP32ES200T","img":"plc","v":[{"n":"24VDC 32 I/O","w":0.38,"l":13.2,"wi":9.0,"h":8.8}]},
        {"name":"ABB ACS355-03E-07A3-4 VFD","model":"ACS355-03E-07A3-4","img":"vfd","v":[{"n":"3kW 3-Phase","w":2.10,"l":23.0,"wi":13.0,"h":18.0}]},
        {"name":"Schneider Altivar ATV320U07N4B VFD","model":"ATV320U07N4B","img":"vfd","v":[{"n":"750W 3-Phase IP20","w":1.40,"l":17.2,"wi":9.2,"h":16.7}]},
        {"name":"Keyence FS-N11P Fiber Sensor","model":"FS-N11P","img":"sensor","v":[{"n":"NPN 2m Cable","w":0.06,"l":8.2,"wi":3.0,"h":6.0}]},
        {"name":"Omron E3Z-D61 Photoelectric Sensor","model":"E3Z-D61","img":"sensor","v":[{"n":"NPN 2m","w":0.04,"l":5.6,"wi":1.5,"h":6.3}]},
        {"name":"Sick DT35-B15251 Distance Sensor","model":"DT35-B15251","img":"sensor","v":[{"n":"0-500mm","w":0.07,"l":4.2,"wi":3.2,"h":1.8}]},
        {"name":"Fanuc Alpha Series Servo Motor","model":"A06B-0235-B605","img":"servo","v":[{"n":"AC 4kW 2000rpm","w":8.50,"l":22.0,"wi":16.5,"h":16.5}]},
        {"name":"Yaskawa SGMJV-04A Servo Drive","model":"SGDV-2R8A01A002000","img":"servo","v":[{"n":"400W 100-200VAC","w":0.90,"l":14.0,"wi":6.8,"h":15.5}]},
        {"name":"Beckhoff EK1100 EtherCAT Coupler","model":"EK1100","img":"plc","v":[{"n":"EtherCAT Bus","w":0.10,"l":4.4,"wi":10.0,"h":"6.8"}]},
        {"name":"Festo DSBC-63-100-PPSA Cylinder","model":"DSBC-63-100-PPSA-N3","img":"pneumatic","v":[{"n":"63mm 100mm Stroke","w":0.80,"l":23.0,"wi":9.0,"h":9.0}]},
        {"name":"SMC AF40-N04D Air Filter","model":"AF40-N04D","img":"pneumatic","v":[{"n":"1/2 inch Port","w":0.42,"l":11.0,"wi":8.5,"h":15.5}]},
        {"name":"Phoenix Contact MKDS 3/2 Terminal","model":"1715021","img":"terminal","v":[{"n":"Pack of 50","w":0.15,"l":5.0,"wi":6.2,"h":3.4}]},
        {"name":"IFM AL1321 IO-Link Master","model":"AL1321","img":"sensor","v":[{"n":"8-Port IO-Link","w":0.18,"l":10.0,"wi":6.8,"h":3.0}]},
        {"name":"Cognex In-Sight 2000 Vision System","model":"IS2000M-120-30-000","img":"camera","v":[{"n":"1.2MP 30fps","w":0.24,"l":9.0,"wi":5.0,"h":3.0}]},
        {"name":"Turck Bi5U-M18-AP6X Inductive Sensor","model":"Bi5U-M18-AP6X","img":"sensor","v":[{"n":"M18 5mm PNP","w":0.08,"l":6.8,"wi":1.8,"h":1.8}]},
        {"name":"Rexnord 1060-60 Gear Drive","model":"1060-60","img":"gearbox","v":[{"n":"Ratio 60:1 0.75kW","w":8.20,"l":22.0,"wi":14.0,"h":16.0}]},
        {"name":"Leuze DDLS 200.1-2 Optical Sensor","model":"DDLS 200.1-2","img":"sensor","v":[{"n":"2m Range Laser","w":0.18,"l":9.0,"wi":5.5,"h":2.8}]},
        {"name":"Pepperl+Fuchs UB500-18GM75-E5-V1","model":"UB500-18GM75-E5-V1","img":"sensor","v":[{"n":"Ultrasonic 500mm","w":0.09,"l":7.3,"wi":1.8,"h":1.8}]},
        {"name":"Bosch Rexroth Ball Screw R160520501","model":"R160520501","img":"linear","v":[{"n":"16mm 500mm Travel","w":0.52,"l":55.0,"wi":4.0,"h":4.0}]},
        {"name":"Nord SK 072.1-71L4/TF Gearbox","model":"SK 072.1-71L4/TF","img":"gearbox","v":[{"n":"0.55kW 3-Phase","w":5.20,"l":22.0,"wi":15.0,"h":16.0}]},
        {"name":"Weidmuller WRS 1.5 Terminal Block","model":"1020080000","img":"terminal","v":[{"n":"Pack of 100","w":0.12,"l":5.0,"wi":5.5,"h":4.8}]},
        {"name":"Banner QS30LPQD Photoelectric","model":"QS30LPQD","img":"sensor","v":[{"n":"PNP 9m Range","w":0.14,"l":9.6,"wi":4.3,"h":5.7}]},
        {"name":"Parker D1VW001CNJB Hydraulic Valve","model":"D1VW001CNJB","img":"hydraulic","v":[{"n":"24VDC 60L/min","w":0.68,"l":11.0,"wi":7.0,"h":9.0}]},
    ],
    "medical-equipment": [
        {"name":"Philips IntelliVue MX40 Monitor","model":"866064","img":"medmonitor","v":[{"n":"Wearable Patient","w":0.39,"l":9.0,"wi":8.4,"h":3.1}]},
        {"name":"GE Healthcare MAC 800 ECG Machine","model":"2032005-001","img":"ecg","v":[{"n":"12-Lead Resting","w":3.20,"l":31.6,"wi":26.9,"h":6.1}]},
        {"name":"Mindray DC-30 Ultrasound","model":"DC-30","img":"ultrasound","v":[{"n":"Portable B/W","w":4.80,"l":36.0,"wi":31.0,"h":9.5}]},
        {"name":"Omron HEM-7600T Blood Pressure","model":"HEM-7600T","img":"bloodpressure","v":[{"n":"Upper Arm Wifi","w":0.32,"l":14.0,"wi":9.5,"h":6.5}]},
        {"name":"Nonin 9590 Onyx II Pulse Oximeter","model":"9590","img":"oximeter","v":[{"n":"Fingertip SpO2","w":0.06,"l":6.4,"wi":3.3,"h":3.2}]},
        {"name":"Welch Allyn 3.5V PanOptic Ophthalmoscope","model":"11810","img":"ophthalmoscope","v":[{"n":"Halogen Diagnostic","w":0.24,"l":27.0,"wi":4.5,"h":4.5}]},
        {"name":"Masimo Radical-7 Pulse Oximeter","model":"7360","img":"oximeter","v":[{"n":"Handheld SpO2 CO","w":0.28,"l":12.8,"wi":6.8,"h":3.2}]},
        {"name":"Draeger Evita 600 Ventilator","model":"MS31350","img":"ventilator","v":[{"n":"ICU Ventilator","w":42.0,"l":55.0,"wi":42.0,"h":145.0}]},
        {"name":"Medtronic Puritan Bennett 980","model":"10074093","img":"ventilator","v":[{"n":"Adult/Pediatric","w":28.0,"l":46.0,"wi":38.0,"h":142.0}]},
        {"name":"Carefusion Alaris 8015 Infusion Pump","model":"8015","img":"infusionpump","v":[{"n":"IV Drug Delivery","w":1.80,"l":19.0,"wi":10.5,"h":13.0}]},
        {"name":"Nihon Kohden EEG-2100G Machine","model":"EEG-2100G","img":"eeg","v":[{"n":"32 Channel Digital","w":6.20,"l":38.0,"wi":29.0,"h":11.0}]},
        {"name":"Spacelabs 91369 Patient Monitor","model":"91369","img":"medmonitor","v":[{"n":"Multi-parameter","w":3.80,"l":28.5,"wi":22.3,"h":14.0}]},
        {"name":"Philips HeartStart FRx AED","model":"861304","img":"defibrillator","v":[{"n":"Automated External","w":1.60,"l":27.5,"wi":19.0,"h":8.5}]},
        {"name":"Zoll AED 3 Defibrillator","model":"8600-001000-01","img":"defibrillator","v":[{"n":"CPR feedback AED","w":1.70,"l":28.0,"wi":21.5,"h":6.4}]},
        {"name":"Edan iM50 Portable Monitor","model":"01.21.064765","img":"medmonitor","v":[{"n":"5-Para Color","w":1.60,"l":26.0,"wi":21.0,"h":9.5}]},
        {"name":"Contec CMS8000 ICU Monitor","model":"CMS8000","img":"medmonitor","v":[{"n":"7-Para Waveform","w":2.10,"l":29.5,"wi":22.0,"h":11.5}]},
        {"name":"Bionet FC1400 Fetal Monitor","model":"FC1400","img":"fetalmonitor","v":[{"n":"Dual Probe TOCO","w":1.80,"l":26.0,"wi":21.0,"h":8.0}]},
        {"name":"Siemens ADVIA 120 Hematology Analyzer","model":"10133601","img":"labanalyzer","v":[{"n":"120 Test/hr","w":45.0,"l":50.0,"wi":40.0,"h":60.0}]},
        {"name":"Roche COBAS e411 Immunoassay Analyzer","model":"05994183001","img":"labanalyzer","v":[{"n":"Electrochemiluminescence","w":87.0,"l":76.0,"wi":55.0,"h":55.0}]},
        {"name":"Abbott i-STAT 1 Handheld Analyzer","model":"03P95-25","img":"labanalyzer","v":[{"n":"Point-of-Care Cartridge","w":0.35,"l":13.5,"wi":8.0,"h":3.8}]},
        {"name":"Nihon Kohden NKT-115 Telemetry","model":"NKT-115","img":"medmonitor","v":[{"n":"4-Lead Wireless","w":0.08,"l":9.5,"wi":6.4,"h":2.2}]},
        {"name":"BPL Cardiart 6108T ECG","model":"Cardiart 6108T","img":"ecg","v":[{"n":"12-Lead Thermal","w":2.40,"l":30.0,"wi":23.0,"h":6.0}]},
        {"name":"Mindray MEC-1200 Bedside Monitor","model":"MEC-1200","img":"medmonitor","v":[{"n":"12.1 inch 5-Para","w":2.60,"l":30.0,"wi":22.0,"h":12.0}]},
        {"name":"Nellcor PM10N Pulse Oximeter","model":"PM10N","img":"oximeter","v":[{"n":"Handheld SpO2","w":0.20,"l":11.0,"wi":6.5,"h":3.2}]},
        {"name":"CareFusion LTV 1200 Ventilator","model":"18190-001","img":"ventilator","v":[{"n":"Portable ICU","w":6.30,"l":28.0,"wi":24.0,"h":13.5}]},
    ],
    "agricultural-tech": [
        {"name":"DJI Agras T40 Agricultural Drone","model":"CP.AG.00000064.01","img":"drone","v":[{"n":"40L Tank 40kg Spread","w":24.8,"l":198.6,"wi":198.8,"h":53.5}]},
        {"name":"DJI Agras T20P Spray Drone","model":"CP.AG.00000057.01","img":"drone","v":[{"n":"20L Tank 20kg Spread","w":15.9,"l":138.7,"wi":143.5,"h":54.7}]},
        {"name":"Trimble EZ-Guide 250 GPS System","model":"57505-00","img":"gps","v":[{"n":"Tractor Guidance","w":0.62,"l":18.0,"wi":14.0,"h":6.5}]},
        {"name":"Soil NPK IoT Sensor RS485","model":"JXBS-3001-NPK","img":"sensor","v":[{"n":"0-100% NPK Probe","w":0.28,"l":12.0,"wi":3.8,"h":3.8}]},
        {"name":"Minolta SPAD-502Plus Chlorophyll","model":"SPAD-502Plus","img":"agri","v":[{"n":"Non-destructive","w":0.24,"l":18.0,"wi":9.5,"h":4.5}]},
        {"name":"Grain Moisture Meter PM-8188A","model":"PM-8188A","img":"moisture","v":[{"n":"7-24% Range","w":0.32,"l":19.0,"wi":8.5,"h":4.0}]},
        {"name":"Davis Vantage Pro2 Weather Station","model":"6152","img":"weatherstation","v":[{"n":"Wireless ISS","w":1.40,"l":27.0,"wi":24.0,"h":10.0}]},
        {"name":"Irritrol Drip Irrigation Controller","model":"RAIBIRD-6","img":"irrigation","v":[{"n":"6-Zone WiFi","w":0.38,"l":14.0,"wi":9.5,"h":5.5}]},
        {"name":"Priva Connext Greenhouse Controller","model":"Connext-4","img":"greenhouse","v":[{"n":"4-Zone Climate","w":1.20,"l":20.0,"wi":12.0,"h":8.0}]},
        {"name":"LED Grow Light 600W Samsung LM301","model":"GL600-LM301H","img":"growlight","v":[{"n":"600W Full Spectrum","w":3.80,"l":56.0,"wi":56.0,"h":5.0}]},
        {"name":"Hydroponic NFT 72-Site System","model":"NFT-72-CH","img":"hydroponics","v":[{"n":"72 Plant Sites","w":8.50,"l":240.0,"wi":60.0,"h":40.0}]},
        {"name":"Precision Vacuum Seeder 6-Row","model":"PS-6R-VACUUM","img":"seeder","v":[{"n":"Tractor-mount 6-Row","w":85.0,"l":180.0,"wi":220.0,"h":120.0}]},
        {"name":"Root Zone Temperature Sensor DS18B20","model":"DS18B20-PROBE-IP68","img":"sensor","v":[{"n":"Waterproof -55-125C","w":0.04,"l":20.0,"wi":0.6,"h":0.6}]},
        {"name":"Plant Disease AI Camera","model":"PlantCam-AI-V2","img":"camera","v":[{"n":"5MP WiFi AI","w":0.18,"l":8.0,"wi":6.5,"h":4.5}]},
        {"name":"Poultry Environment Controller","model":"PEC-8CH-V3","img":"controller","v":[{"n":"8-Channel Relay WiFi","w":0.42,"l":18.0,"wi":12.0,"h":8.0}]},
        {"name":"Aquaculture Water Quality Monitor","model":"AQM-4IN1","img":"water","v":[{"n":"pH DO TDS Temp","w":0.38,"l":16.0,"wi":8.0,"h":5.5}]},
        {"name":"Aquaponics Complete Starter System","model":"APS-200L","img":"hydroponics","v":[{"n":"200L Tank+Grow Bed","w":28.0,"l":120.0,"wi":60.0,"h":80.0}]},
        {"name":"GPS Livestock Ear Tag Tracker","model":"LT-GPS-EAR-4G","img":"gps","v":[{"n":"4G LTE IP67","w":0.04,"l":5.0,"wi":4.5,"h":1.0}]},
        {"name":"DJI D-RTK 2 Mobile Station","model":"CP.AG.00000015.02","img":"drone","v":[{"n":"RTK Base Station","w":0.49,"l":16.7,"wi":16.7,"h":10.6}]},
        {"name":"Cold Room Controller EBM-20","model":"EBM-20-230VAC","img":"controller","v":[{"n":"Defrost+Alarm 2 Probe","w":0.22,"l":12.0,"wi":7.5,"h":5.5}]},
        {"name":"Fruit Brix Refractometer Digital","model":"PAL-BX|ACID97","img":"agri","v":[{"n":"0-85% Brix IP65","w":0.08,"l":14.0,"wi":3.0,"h":3.0}]},
        {"name":"Automated Fertigation Controller","model":"FC-6ZONE-PRO","img":"irrigation","v":[{"n":"6-Channel NPK EC pH","w":0.85,"l":20.0,"wi":14.0,"h":8.0}]},
        {"name":"Soil Moisture Sensor Capacitive v2","model":"CAP-SOIL-V2","img":"sensor","v":[{"n":"3-5V Analog Digital","w":0.02,"l":9.8,"wi":2.3,"h":0.3}]},
        {"name":"Vertical Farm Rack LED System","model":"VF-RACK-1200W","img":"growlight","v":[{"n":"1200W 4-Tier 2m","w":18.0,"l":200.0,"wi":60.0,"h":210.0}]},
        {"name":"Solar Powered Irrigation Pump 24V","model":"SIP-750W-24V","img":"pump","v":[{"n":"750W 40m Head","w":4.20,"l":32.0,"wi":15.0,"h":15.0}]},
    ],
    "clean-energy-ev": [
        {"name":"Growatt SPF 5000ES Solar Inverter","model":"SPF 5000 ES","img":"solarinverter","v":[{"n":"5kW Off-Grid 48V","w":11.5,"l":46.5,"wi":36.5,"h":14.5}]},
        {"name":"Huawei SUN2000-10KTL-M1 Inverter","model":"SUN2000-10KTL-M1","img":"solarinverter","v":[{"n":"10kW Grid-Tie 3Ph","w":22.0,"l":52.5,"wi":47.0,"h":17.5}]},
        {"name":"SMA Sunny Boy 3.6-1AV-41 Inverter","model":"SB3.6-1AV-41","img":"solarinverter","v":[{"n":"3.6kW 1Ph Grid-Tie","w":13.5,"l":44.0,"wi":26.4,"h":17.6}]},
        {"name":"Deye SUN-8K-SG04LP3 Hybrid Inverter","model":"SUN-8K-SG04LP3-EU","img":"solarinverter","v":[{"n":"8kW Hybrid 48V","w":16.0,"l":46.5,"wi":36.5,"h":14.5}]},
        {"name":"KSTAR BluE-S 6KT Hybrid Inverter","model":"BluE-S 6KT","img":"solarinverter","v":[{"n":"6kW Hybrid LiFePO4","w":15.0,"l":44.0,"wi":32.5,"h":14.5}]},
        {"name":"EV AC Charger Wallbox Pulsar Plus 22kW","model":"PLP1-0-2-4-9-002-C","img":"evcharger","v":[{"n":"22kW Type2 WiFi","w":2.30,"l":17.6,"wi":15.4,"h":9.3}]},
        {"name":"EV DC Fast Charger 50kW CCS CHAdeMO","model":"EVC-50-DC-DUAL","img":"evcharger","v":[{"n":"50kW Dual Output","w":85.0,"l":75.0,"wi":55.0,"h":165.0}]},
        {"name":"CATL LiFePO4 280Ah Grade A Cell","model":"EVE-LF280K","img":"battery","v":[{"n":"3.2V 280Ah Prismatic","w":0.54,"l":17.4,"wi":7.2,"h":20.7}]},
        {"name":"BYD Battery Box Premium LVS 4.0","model":"BYD-LVS-4.0","img":"battery","v":[{"n":"3.84kWh 48V Stack","w":25.0,"l":44.0,"wi":22.0,"h":22.0}]},
        {"name":"Solar Panel 550W Mono PERC Risen","model":"RSM110-8-550M","img":"solarpanel","v":[{"n":"182mm Half-Cell","w":28.0,"l":225.7,"wi":113.4,"h":3.5}]},
        {"name":"Solar Panel 400W Bifacial Longi","model":"LR5-54HTH-400M","img":"solarpanel","v":[{"n":"400W Bifacial PERC","w":21.3,"l":172.2,"wi":113.5,"h":3.0}]},
        {"name":"Victron MPPT 100/50 Charge Controller","model":"SCC020050200","img":"chargecontroller","v":[{"n":"100V 50A SmartSolar","w":0.59,"l":18.5,"wi":10.0,"h":6.7}]},
        {"name":"Victron MultiPlus-II 48/3000/35-32","model":"PMP482305010","img":"inverter","v":[{"n":"3kW 48V Inverter-Charger","w":16.8,"l":40.0,"wi":27.0,"h":22.7}]},
        {"name":"CATL 10kWh LiFePO4 Home Battery","model":"CATL-HBS-10","img":"battery","v":[{"n":"48V 200Ah Rackmount","w":98.0,"l":48.0,"wi":60.0,"h":22.0}]},
        {"name":"Lithium Pack 48V 200Ah LiFePO4","model":"LP48V200AH-BMS","img":"battery","v":[{"n":"10.24kWh with 100A BMS","w":42.0,"l":48.5,"wi":27.0,"h":22.5}]},
        {"name":"EV Conversion Kit 72V 3000W","model":"EVCK-72V-3000W-BLDC","img":"evmotor","v":[{"n":"BLDC Hub Motor Kit","w":12.0,"l":35.0,"wi":20.0,"h":15.0}]},
        {"name":"E-Bike Rear Hub Motor Kit 1000W","model":"EBHM-1000W-48V-RR","img":"evmotor","v":[{"n":"48V 26 inch Rear","w":5.50,"l":28.0,"wi":28.0,"h":8.5}]},
        {"name":"Solar Street Light 100W All-in-One","model":"SSL-100W-AIO-6M","img":"streetlight","v":[{"n":"100W 6m Pole","w":4.80,"l":62.0,"wi":28.0,"h":8.0}]},
        {"name":"Heat Pump Water Heater 200L","model":"HPWH-200L-3.8COP","img":"heatpump","v":[{"n":"200L 1.2kW COP 3.8","w":95.0,"l":55.0,"wi":55.0,"h":160.0}]},
        {"name":"Portable Power Station Jackery 1000","model":"Explorer-1000-Pro","img":"powerstation","v":[{"n":"1002Wh LiFePO4","w":9.10,"l":33.0,"wi":17.7,"h":23.0}]},
        {"name":"Wind Turbine 1kW 24V Horizontal","model":"WT-1000W-H24V-3B","img":"windturbine","v":[{"n":"3-Blade 1kW 2.5m/s","w":18.0,"l":120.0,"wi":15.0,"h":15.0}]},
        {"name":"EV Charging RFID Card Controller","model":"EV-OCPP-16A-RFID","img":"evcharger","v":[{"n":"16A OCPP 1.6 RFID","w":1.20,"l":20.0,"wi":14.5,"h":8.5}]},
        {"name":"Solar Panel Mounting Rail 4m","model":"SOLAR-RAIL-AL-4M","img":"solarpanel","v":[{"n":"Aluminium 4m 2-Panel","w":3.80,"l":400.0,"wi":4.0,"h":4.5}]},
        {"name":"48V 60Ah LiFePO4 E-Rickshaw Battery","model":"LP48V60AH-EV-BMS","img":"battery","v":[{"n":"2.88kWh IP55","w":18.0,"l":32.0,"wi":18.0,"h":22.5}]},
        {"name":"EV Charge Point OCPP Cloud Manager","model":"EV-CLOUD-OCPP-16","img":"evcharger","v":[{"n":"16-Port OCPP 2.0","w":1.80,"l":22.0,"wi":16.0,"h":10.0}]},
    ],
    "scientific-instruments": [
        {"name":"Rigol DS1054Z Digital Oscilloscope","model":"DS1054Z","img":"oscilloscope","v":[{"n":"100MHz 4Ch 12Mpts","w":2.27,"l":30.5,"wi":15.3,"h":13.3}]},
        {"name":"Siglent SDG2042X Function Generator","model":"SDG2042X","img":"functiongen","v":[{"n":"40MHz AWG 256Mpts","w":2.80,"l":33.3,"wi":24.2,"h":10.8}]},
        {"name":"Fluke 87V Industrial Multimeter","model":"87V","img":"multimeter","v":[{"n":"True-RMS Cat III","w":0.35,"l":19.5,"wi":9.5,"h":5.5}]},
        {"name":"GW Instek LCR-819 Precision Meter","model":"LCR-819","img":"lcrmeter","v":[{"n":"12Hz-200kHz 0.1%","w":2.40,"l":25.3,"wi":19.4,"h":10.0}]},
        {"name":"Rigol DSA875-TG Spectrum Analyzer","model":"DSA875-TG","img":"spectrum","v":[{"n":"9kHz-7.5GHz TG","w":5.40,"l":35.5,"wi":23.8,"h":16.8}]},
        {"name":"NanoVNA-F V2 4.4GHz Vector Analyzer","model":"NANOVNA-F-V2","img":"vna","v":[{"n":"50kHz-4.4GHz SAA-2","w":0.23,"l":11.3,"wi":7.5,"h":1.4}]},
        {"name":"Korad KA3005P Bench Power Supply","model":"KA3005P","img":"powersupply","v":[{"n":"30V 5A Programmable","w":2.20,"l":25.5,"wi":15.5,"h":11.0}]},
        {"name":"Hakko FX-951 Soldering Station","model":"FX951-66","img":"soldering","v":[{"n":"70W T12 Tips","w":0.55,"l":13.3,"wi":12.5,"h":5.2}]},
        {"name":"T962A PCB Reflow Oven 300x320mm","model":"T962A","img":"reflow","v":[{"n":"1500W SMD Reflow","w":10.5,"l":44.5,"wi":37.5,"h":15.5}]},
        {"name":"Sartorius ME235S Analytical Balance","model":"ME235S","img":"balance","v":[{"n":"230g 0.00001g","w":8.70,"l":37.0,"wi":28.5,"h":16.0}]},
        {"name":"Hanna HI98130 pH/EC/TDS Meter","model":"HI98130","img":"phmeter","v":[{"n":"0-14pH +/-0.1","w":0.08,"l":16.5,"wi":3.2,"h":2.8}]},
        {"name":"Shimadzu UV-1900i Spectrophotometer","model":"UV-1900i","img":"spectro","v":[{"n":"190-1100nm 0.5nm","w":14.0,"l":45.5,"wi":39.5,"h":24.0}]},
        {"name":"Trinocular Microscope BM2000","model":"BM2000-T-LED","img":"microscope","v":[{"n":"40x-2000x Fluorescent","w":4.20,"l":22.0,"wi":17.0,"h":42.0}]},
        {"name":"Dino-Lite AM7515MT8A Digital Microscope","model":"AM7515MT8A","img":"microscope","v":[{"n":"720p 5MP 20-220x","w":0.10,"l":10.5,"wi":3.3,"h":3.3}]},
        {"name":"FLIR One Pro iOS Thermal Camera","model":"435-0011-03","img":"thermal","v":[{"n":"160x120 +/-3°C","w":0.08,"l":8.7,"wi":4.9,"h":2.1}]},
        {"name":"Saleae Logic Pro 16 USB Analyzer","model":"LOGIC-PRO-16","img":"logicanalyzer","v":[{"n":"16-Channel 500MSps","w":0.06,"l":6.5,"wi":4.0,"h":1.3}]},
        {"name":"Segger J-Link BASE Compact","model":"8.19.00","img":"jtag","v":[{"n":"JTAG/SWD Debugger","w":0.04,"l":5.5,"wi":3.8,"h":1.1}]},
        {"name":"Weiss Technik WK 3-40/40 Chamber","model":"WK 3-40/40","img":"testchamber","v":[{"n":"-40 to +180°C 64L","w":98.0,"l":52.0,"wi":52.0,"h":78.0}]},
        {"name":"MSA Altair 4XR Gas Detector","model":"10128840","img":"gasdetector","v":[{"n":"4-Gas LEL O2 CO H2S","w":0.24,"l":11.8,"wi":6.7,"h":3.6}]},
        {"name":"PCE-322A Sound Level Meter","model":"PCE-322A","img":"soundmeter","v":[{"n":"30-130dB Class 2","w":0.18,"l":23.0,"wi":6.0,"h":3.2}]},
        {"name":"Keysight 34461A Bench Multimeter","model":"34461A-G","img":"multimeter","v":[{"n":"6.5 Digit True-RMS","w":2.40,"l":26.3,"wi":21.7,"h":"8.8"}]},
        {"name":"Siglent SDS1202X-E Oscilloscope","model":"SDS1202X-E","img":"oscilloscope","v":[{"n":"200MHz 2Ch 14Mpts","w":2.07,"l":30.5,"wi":15.3,"h":13.3}]},
        {"name":"Extech AN200 Anemometer","model":"AN200","img":"anemometer","v":[{"n":"0.4-30m/s Temp Humid","w":0.12,"l":20.0,"wi":5.5,"h":3.2}]},
        {"name":"Endress+Hauser Prosonic M FMU40","model":"FMU40-ARB2A2","img":"sensor","v":[{"n":"Ultrasonic Level","w":0.38,"l":28.0,"wi":8.5,"h":8.5}]},
        {"name":"Rohde Schwarz RTM3004 Oscilloscope","model":"RTM3004","img":"oscilloscope","v":[{"n":"200MHz 4Ch 1GSps","w":4.20,"l":35.0,"wi":19.5,"h":16.0}]},
    ],
    "3d-printing-maker": [
        {"name":"Bambu Lab X1 Carbon 3D Printer","model":"X1C-Combo","img":"3dprinter","v":[{"n":"256x256x256mm 600mm/s","w":14.9,"l":38.9,"wi":38.9,"h":45.7}]},
        {"name":"Creality K1 Max FDM 3D Printer","model":"K1-Max","img":"3dprinter","v":[{"n":"300x300x300mm 600mm/s","w":23.3,"l":50.4,"wi":56.4,"h":51.8}]},
        {"name":"Elegoo Saturn 3 Ultra MSLA Printer","model":"Saturn-3-Ultra","img":"3dprinter","v":[{"n":"218x123x260mm 14K","w":7.20,"l":31.0,"wi":27.3,"h":50.5}]},
        {"name":"Prusa MK4 3D Printer Kit","model":"MK4S","img":"3dprinter","v":[{"n":"250x210x220mm Klipper","w":7.30,"l":50.0,"wi":50.0,"h":50.0}]},
        {"name":"Bambu Lab P1S 3D Printer","model":"P1S-Combo","img":"3dprinter","v":[{"n":"256x256x256mm Enclosed","w":14.5,"l":38.9,"wi":38.9,"h":45.7}]},
        {"name":"AnkerMake M5C 3D Printer","model":"M5C","img":"3dprinter","v":[{"n":"220x220x250mm 500mm/s","w":7.60,"l":36.5,"wi":36.5,"h":48.0}]},
        {"name":"Formlabs Form 3L SLA Printer","model":"Form 3L","img":"3dprinter","v":[{"n":"33x20x30cm Low-Force","w":26.5,"l":61.0,"wi":45.7,"h":74.0}]},
        {"name":"Bambu Lab AMS Multi-filament Unit","model":"AMS","img":"3dprinter","v":[{"n":"4-Color AMS","w":3.30,"l":32.9,"wi":22.6,"h":15.5}]},
        {"name":"Raspberry Pi 5 8GB RAM","model":"SC1112","img":"raspberrypi","v":[{"n":"Cortex-A76 2.4GHz","w":0.05,"l":8.5,"wi":5.6,"h":1.7}]},
        {"name":"NVIDIA Jetson Orin Nano 8GB","model":"945-13766-0050-000","img":"jetson","v":[{"n":"1024 CUDA 40TOPs","w":0.28,"l":8.7,"wi":5.0,"h":4.1}]},
        {"name":"NVIDIA Jetson Nano 4GB Developer Kit","model":"945-13450-0000-100","img":"jetson","v":[{"n":"128 CUDA 472GFLOPs","w":0.37,"l":10.0,"wi":7.9,"h":4.5}]},
        {"name":"Arduino Mega 2560 R3 Official","model":"A000067","img":"arduino","v":[{"n":"AVR 54 Digital Pins","w":0.05,"l":10.2,"wi":5.4,"h":1.1}]},
        {"name":"Raspberry Pi Pico 2 W","model":"SC1632","img":"raspberrypi","v":[{"n":"RP2350 WiFi BT","w":0.01,"l":5.1,"wi":2.1,"h":0.6}]},
        {"name":"xTool D1 Pro 20W Laser Engraver","model":"D1-Pro-20W","img":"laserengraver","v":[{"n":"430x390mm 20W","w":4.50,"l":65.0,"wi":55.0,"h":24.0}]},
        {"name":"CNC 3018 Pro Max Router GRBL","model":"3018-ProMax","img":"cnc","v":[{"n":"300x180x45mm 5500rpm","w":3.80,"l":40.0,"wi":35.0,"h":25.0}]},
        {"name":"PLA+ Filament 3kg Bundle Bambu","model":"PLA-PLUS-3KG-WHITE","img":"filament","v":[{"n":"1.75mm ±0.02mm","w":3.20,"l":26.0,"wi":26.0,"h":8.0}]},
        {"name":"PETG Carbon Fiber Filament 1kg","model":"PETG-CF-1KG","img":"filament","v":[{"n":"1.75mm 15% CF","w":1.20,"l":22.0,"wi":22.0,"h":7.0}]},
        {"name":"TPU 95A Flexible Filament 1kg","model":"TPU95A-1KG-BLK","img":"filament","v":[{"n":"1.75mm Shore 95A","w":1.10,"l":22.0,"wi":22.0,"h":7.0}]},
        {"name":"Elegoo 405nm ABS-Like UV Resin 1L","model":"EL-3D-RESIN-1L","img":"resin","v":[{"n":"1L Grey ABS-Like","w":1.30,"l":12.0,"wi":8.5,"h":21.5}]},
        {"name":"Google Coral USB Accelerator TPU","model":"G950-06809-01","img":"jetson","v":[{"n":"4 TOPs USB 3.0","w":0.06,"l":6.5,"wi":3.0,"h":0.8}]},
        {"name":"Intel RealSense D435i Depth Camera","model":"82635AWGDVKPRQ","img":"camera","v":[{"n":"30fps Depth+IMU","w":0.07,"l":9.0,"wi":2.5,"h":2.5}]},
        {"name":"Luxonis OAK-D Lite Spatial Camera","model":"OAK-D-LITE-FF","img":"camera","v":[{"n":"Fixed-Focus Depth AI","w":0.06,"l":9.1,"wi":2.8,"h":3.0}]},
        {"name":"Creality Ender 3 V3 KE 3D Printer","model":"Ender-3-V3-KE","img":"3dprinter","v":[{"n":"220x220x240mm 500mm/s","w":7.80,"l":38.5,"wi":38.5,"h":44.0}]},
        {"name":"ESP32-S3 Dev Kit N16R8","model":"ESP32-S3-DevKitC-1","img":"arduino","v":[{"n":"240MHz WiFi BT 16MB","w":0.01,"l":6.9,"wi":2.8,"h":0.8}]},
        {"name":"Jetson Xavier NX 16GB Module","model":"900-83668-0030-000","img":"jetson","v":[{"n":"384 CUDA 21TOPs","w":0.04,"l":6.9,"wi":4.5,"h":1.0}]},
    ],
}

# Image keyword per category
IMG_KEYWORDS = {
    "industrial-automation": {"plc":"plc,automation","vfd":"vfd,motor,drive","sensor":"sensor,industrial","servo":"servo,motor","pneumatic":"pneumatic,valve","terminal":"terminal,block,electrical","gearbox":"gearbox,motor","linear":"linear,guide,cnc","hydraulic":"hydraulic,valve","camera":"vision,camera,inspection"},
    "medical-equipment": {"medmonitor":"patient,monitor,hospital","ecg":"ecg,machine","ultrasound":"ultrasound,machine","bloodpressure":"blood,pressure,monitor","oximeter":"pulse,oximeter","ophthalmoscope":"ophthalmoscope,medical","ventilator":"ventilator,icu","infusionpump":"infusion,pump,iv","eeg":"eeg,brain,monitor","labanalyzer":"lab,analyzer,medical","defibrillator":"defibrillator,aed","fetalmonitor":"fetal,monitor"},
    "agricultural-tech": {"drone":"agricultural,drone","gps":"gps,agriculture","sensor":"soil,sensor","agri":"agriculture,field","moisture":"grain,moisture","weatherstation":"weather,station","irrigation":"irrigation,controller","greenhouse":"greenhouse","growlight":"grow,light,led","hydroponics":"hydroponics","seeder":"seeder,agriculture","water":"water,quality,sensor","controller":"farm,controller","camera":"plant,camera","pump":"water,pump"},
    "clean-energy-ev": {"solarinverter":"solar,inverter","evcharger":"ev,charger","battery":"lithium,battery","solarpanel":"solar,panel","chargecontroller":"solar,charge,controller","inverter":"inverter,power","evmotor":"electric,motor","streetlight":"solar,street,light","heatpump":"heat,pump","powerstation":"power,station","windturbine":"wind,turbine"},
    "scientific-instruments": {"oscilloscope":"oscilloscope","functiongen":"function,generator","multimeter":"multimeter,fluke","lcrmeter":"lcr,meter","spectrum":"spectrum,analyzer","vna":"vector,network,analyzer","powersupply":"bench,power,supply","soldering":"soldering,station","reflow":"reflow,oven,pcb","balance":"analytical,balance","phmeter":"ph,meter","spectro":"spectrophotometer","microscope":"microscope,lab","thermal":"thermal,camera","logicanalyzer":"logic,analyzer","jtag":"jtag,debugger","testchamber":"test,chamber","gasdetector":"gas,detector","soundmeter":"sound,level,meter","anemometer":"anemometer"},
    "3d-printing-maker": {"3dprinter":"3d,printer","raspberrypi":"raspberry,pi","jetson":"nvidia,jetson","arduino":"arduino","laserengraver":"laser,engraver","cnc":"cnc,router","filament":"3d,filament","resin":"uv,resin","camera":"depth,camera"},
}

class Command(BaseCommand):
    help = "Seed 6 import-demand categories with 25 products each"

    def handle(self, *args, **options):
        total = 0

        for cat_data in NEW_CATEGORIES:
            cat, created = Category.objects.get_or_create(
                slug=cat_data["slug"],
                defaults={"name": cat_data["name"]},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created category: {cat.name}"))
            else:
                self.stdout.write(f"Category exists: {cat.name}")

        for cat_slug, product_list in PRODUCTS.items():
            cat = Category.objects.get(slug=cat_slug)
            kw_map = IMG_KEYWORDS.get(cat_slug, {})
            added = 0

            for idx, pd in enumerate(product_list):
                slug = slugify(pd["name"])
                if Product.objects.filter(slug=slug).exists():
                    continue

                img_key = pd.get("img", "product")
                keyword = kw_map.get(img_key, img_key)
                lock = 2000 + idx * 11 + sum(ord(c) for c in cat_slug) % 200

                product = Product.objects.create(
                    name=pd["name"],
                    slug=slug,
                    model=pd.get("model", ""),
                    category=cat,
                    image_url=f"https://loremflickr.com/400/400/{keyword}?lock={lock}",
                )

                for v in pd.get("v", []):
                    ProductVariant.objects.create(
                        product=product,
                        variant_name=v["n"],
                        weight_kg=float(str(v["w"]).replace('"','')),
                        length_cm=float(str(v["l"]).replace('"','')),
                        width_cm=float(str(v["wi"]).replace('"','')),
                        height_cm=float(str(v["h"]).replace('"','')),
                    )

                added += 1
                total += 1
                self.stdout.write(f"  ADD [{cat.name}] {product.name}")

            count = Product.objects.filter(category=cat).count()
            self.stdout.write(self.style.SUCCESS(f"  {cat.name}: +{added} added, total={count}"))

        self.stdout.write(self.style.SUCCESS(f"\nDone -- {total} new products created."))
